import hashlib
import json
from time import time
from textwrap import dedent
from uuid import uuid4
from urllib.parse import urlparse
from flask import Flask, jsonify, request
import requests

class Blockchain(object):
    #Initalize our chain to be an empty list
    def __init__(self):
        #stores data
        self.chain = []
        self.currentTransactions = []
        #use a set to ensure each node can only be added once
        self.nodes = set()
        #create the genesis block
        self.new_block(previous_hash=1, proof=100)

    #Add a node to the list of nodes
    def register_nodes(self, address):
        parsed_url= urlparse(address)
        self.nodes.add(parsed_url.netloc)

    #create a new block and add it to the block chain
    def new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) +1,
            'timestamp': time(),
            'transactions': self.currentTransactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        self.currentTransactions = []
        self.chain.append(block)
        return block

    #adds new transaction to list of transactions
    def new_transaction(self,sender,recipient, amount):
        self.currentTransactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })
        #returns the index of the next block to be mined
        return self.last_block['index'] + 1

    #determines if a given chain is valid
    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block=chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n---------\n")
            #check the block's hash
            if block['previous_hash'] != self.hash(last_block):
                return False
            #check the pow is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            last_block = block
            current_index += 1
        
        return True
    #reaches a consensus between nodes by making the longest chain the valid one    
    def resolve_conflicts(self):
        neighbors = self.nodes
        new_chain = None
        
        max_length = len(self.chain)

        #check each nodes chain for length
        for node in neighbors:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                #replace our chain if new one is valid and longer than ours
                if (length > max_length and self.valid_chain(chain)):
                    max_length = length
                    new_chain = chain
        if new_chain:
            self.chain = new_chain
            return True
        
        return False

            


    
    #returns the last block in the chain
    @property
    def last_block(self):
        return self.chain[-1]

    #hashes the information in a block
    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    #find a number such that when hashed with the prior proof leads to 4 leading zeroes
    def proof_of_work(self, last_proof):
        
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof +=1

        return proof

    #checks if the proof meets the proof of work critera of 4 leading zeroes
    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

#create a node
app = Flask(__name__)

#give this node a unique address
node_identifier = str(uuid4()).replace('-', '')

#Create a block chain
blockchain = Blockchain()

#mining end point, calculates the proof of work, rewards the miner and adds the new block to the chain
@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    #reward the miner with a coin for finding the pow
    blockchain.new_transaction(sender="0",recipient= node_identifier,amount=1)
    
    #create the new block
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'Message': "New Block Forged",
        'index': block['index'],
        'transaction': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

#recieves information from the request and adds it to the transaction list
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    
    required = ['sender', 'recipient', 'amount']
    
    #checks to make sure request has values for sender recipient and amount
    if not all(k in values for k in required):
        return 'Missing values', 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201

#returns information on the chain
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

#route to add nodes to nodes list
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.register_nodes(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201
#route to trigger consensus between chains
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain,
        }
    else:
        response = {
            'message': 'Our chain is authorative',
            'new_chain': blockchain.chain,
        }
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

    
