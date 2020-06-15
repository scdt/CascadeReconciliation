import random
import os
import time
import pickle
from bitarray import bitarray
from bitarray import util

class Block:
	def __init__(self, indx, length, bits, errorIndex=-1, iteration=0, parity=-1, correctParity=-1):
		self.index=indx
		self.length=length
		self.bitArray=bits
		self.errorIndex=errorIndex
		self.iteration=iteration
		self.parity=parity
		self.correctParity=correctParity
	def CalculateBlockParity(self):
		if self.parity!=-1:
			return self.parity
		self.parity=self.bitArray.count(True)%2
		return self.parity

def RandomBitArray(length, fileName='randomKey'):
	f=open(fileName, 'wb')
	f.write(os.urandom(length))
	f.close()
	f=open(fileName, 'rb')
	bits=bitarray()
	bits.fromfile(f)
	f.close()
	return bits

def AddNoise(qber, fileName='randomKey'):
	f=open(fileName, 'rb')
	bits=bitarray()
	bits.fromfile(f)
	f.close()
	for i in range(int(round(bits.length()*qber))):
		j=random.randrange(bits.length())
		bits[j]= not bits[j]
	f=open('rawKey', 'wb')
	f.write(bits)
	f.close()
	return bits

def EstimateQBER(rawKey, correctBits):
	errors=0.0
	for i in range(correctBits.length()):
		if correctBits[i]!=rawKey[i]:
			errors+=1
	return errors/correctBits.length()

def GetBitArray(fileName='randomKey'):
	f=open(fileName, 'rb')
	bits=bitarray()
	bits.fromfile(f)
	f.close()
	return bits

def AskAliceBlockParity(block, shuffles_fromPrev, sock=None):
	if block.correctParity!=-1:
		return block.correctParity
	global parity_requests
	parity_requests+=1
	indexes=[]
	for i in range(block.index,block.index+block.length):
		index=i
		for j in range(block.iteration,-1,-1):
			index=shuffles_fromPrev[j][index]
		indexes.append(index)
	if sock==None:
		bits=bitarray([correctKey[i] for i in indexes])
		block.correctParity=bits.count(True)%2
	else:
		sock.send(pickle.dumps(indexes))
		parity=sock.recv(1)
		if parity:
			block.correctParity=1
		else:
			block.correctParity=0
	return block.correctParity

def GetCorrespondingBlock(shuffles_fromPrev, iteration, currentIteration, currentErrorIndex):
	blockLength=GetBlockLen(iteration)
	errorIndex=currentErrorIndex
	for i in range(currentIteration,iteration-1,-1):
		errorIndex=shuffles_fromPrev[i][errorIndex]
	index=errorIndex-errorIndex%blockLength
	if index+blockLength>len(iterationKeys[0]):
		blockLength=blockLength-(index+blockLength)%len(iterationKeys[0])
	return Block(index, blockLength, iterationKeys[iteration][index:index+blockLength], errorIndex, iteration)

def GetIterationBlocks(key, iteration):	
	blockLength=GetBlockLen(iteration)
	blocks=[Block(i,blockLength,key[i:i+blockLength], -1, iteration) for i in range(0,key.length()-key.length()%blockLength,blockLength)]
	blocksLength=len(blocks)*blockLength
	blocks.append(Block(blockLength*len(blocks),key.length()-blocksLength,key[blockLength*len(blocks):], -1, iteration))
	return blocks

def GetBlockLen(iteration):
	return int(round(0.73/qber)*(2**iteration))

def ShuffleNoRepeats(shuffles_fromFirst, length):
	shuffle=list(range(length))
	shuffles=[[],[]]
	if not shuffles_fromFirst:
		shuffles[0]=shuffle
		shuffles[1]=shuffle
		return shuffles
	newShuffle=list(range(length))
	newShuffle_fromPrev=list(range(length))
	rnd=0
	rnd_stop=1
	for i in range(length-rnd_stop):
		repeat=True
		count=0
		while repeat:
			k=count
			rnd=random.randrange(length-i)
			for j in range(len(shuffles_fromFirst)):
				if shuffle[rnd]==shuffles_fromFirst[j][i]:
					count+=1
					break
			if k==count:
				repeat=False
				newShuffle[i]=shuffle[rnd]
				shuffle.pop(rnd)
				break
			if count>=100:
				print("count")
				break
	for i in range(length-rnd_stop,length):
		repeat=False
		for j in range(len(shuffles_fromFirst)):
				if shuffle[i-length+rnd_stop]==shuffles_fromFirst[j][i]:
					repeat=True
					break
		if not repeat:
			newShuffle[i]=shuffle[i-length+rnd_stop]
		else:
			break
	else:
		for i in range(length):
			newShuffle_fromPrev[newShuffle[i]]=shuffles_fromFirst[len(shuffles_fromFirst)-1][i]
		shuffles[0]=newShuffle
		shuffles[1]=newShuffle_fromPrev
		return shuffles
	return ShuffleNoRepeats(shuffles_fromFirst, length)

def Rearrange(anyKey, shuffle):
	shuffled=bitarray(anyKey)
	for i in range(anyKey.length()):
		shuffled[shuffle[i]]=anyKey[i]
	return shuffled

def FlipBit(shuffles_fromPrev, shuffles_fromFirst, iteration, lastIteration, errorIndex):
	index=errorIndex
	for i in range(iteration,-1,-1):
		iterationKeys[i][index]=not iterationKeys[i][index]
		index=shuffles_fromPrev[i][index]
	for i in range(iteration+1, lastIteration+1):
		j=shuffles_fromFirst[i][index]
		iterationKeys[i][j]= not iterationKeys[i][j]
def Binary(block, iteration, shuffles_fromPrev):
	if block.length==1:
		return block.index
	else:
		if block.length%2:
			lh_length=block.length//2+1
			rh_length=block.length//2
		else:
			lh_length=block.length//2
			rh_length=lh_length
		lh=Block(block.index, lh_length, block.bitArray[:lh_length], -1, iteration)
		lh_correctParity=AskAliceBlockParity(lh, shuffles_fromPrev)
		lh_currentParity=lh.CalculateBlockParity()
		if lh_currentParity!=lh_correctParity:
			return Binary(lh, iteration, shuffles_fromPrev)
		else:
			rh=Block(block.index+lh_length, rh_length, block.bitArray[lh_length:])
			return Binary(rh, iteration, shuffles_fromPrev)

def Cascade(fileName, iterations, sock=None, knownQBER=None):
	global iterationKeys
	global qber
	global correctKey
	rawKey=GetBitArray(fileName)
	if not knownQBER:
		if sock:
			sock.sendall(b'Cascade qber estimation')
			data=sock.recieve(rawKey.length//16+2)
			correctBits=bitarray()
			correctBits.frombytes(data)
			correctBits=correctBits[:rawKey.length()//2]
		else:
			correctBits=correctKeyFull[:rawKey.length()//2]
		qber=EstimateQBER(rawKey, correctBits)
		rawKey=rawKey[rawKey.length()//2:]
	else:
		qber=knownQBER
		if sock:
			sock.send(b'Cascade')
		else:
			correctKey=correctKeyFull
	iterationKeys=[]
	shuffles_fromFirst=[]
	shuffles_fromPrev=[]
	for i in range(iterations):
		shuffles=ShuffleNoRepeats(shuffles_fromFirst,rawKey.length())
		shuffles_fromFirst.append(shuffles[0])
		shuffles_fromPrev.append(shuffles[1])
		if i>=1:
			rawKey=Rearrange(iterationKeys[0], shuffles_fromFirst[i])
		iterationKeys.append(rawKey)
		iterationBlocks=GetIterationBlocks(iterationKeys[i], i)
		currentBlockParities=[block.CalculateBlockParity() for block in iterationBlocks]
		correctBlockParities=[AskAliceBlockParity(block, shuffles_fromPrev) for block in iterationBlocks]
		for j in range(len(currentBlockParities)):
			if correctBlockParities[j]!=currentBlockParities[j]:
				errorIndex=Binary(iterationBlocks[j], i, shuffles_fromPrev)
				FlipBit(shuffles_fromPrev, shuffles_fromFirst, i, i, errorIndex)
				if i>=1:
					CascadeEffect(shuffles_fromPrev, shuffles_fromFirst, i, errorIndex)
					### may be there are more efficient way to get corrected parities
					iterationBlocks=GetIterationBlocks(iterationKeys[i], i)
					currentBlockParities=[block.CalculateBlockParity() for block in iterationBlocks]
	return iterationKeys[0]

def CascadeEffect(shuffles_fromPrev, shuffles_fromFirst, lastIteration, firstErrorIndex):
	errorBlocks=[]
	currentIteration=lastIteration
	currentErrorIndex=firstErrorIndex
	count=0
	while True:
		count+=1
		for i in range(lastIteration+1):
			if i!=currentIteration:
				block=GetCorrespondingBlock(shuffles_fromPrev, i, currentIteration, currentErrorIndex)
				block_in_errorBlocks=False
				for b in errorBlocks:
					if block.index==b.index and block.length==b.length:
						block_in_errorBlocks=True
				if not block_in_errorBlocks:
					errorBlocks.append(block)
					errorBlocks.sort(key=lambda k: k.length)
		try:
			errorBlock=errorBlocks.pop()
		except Exception:
			print('Exception: pop from empty!')
		### while added
		while errorBlock.CalculateBlockParity()==AskAliceBlockParity(errorBlock, shuffles_fromPrev) and errorBlocks:
			errorBlock=errorBlocks.pop()
		if errorBlock.parity!=errorBlock.correctParity:
			currentIteration=errorBlock.iteration
			currentErrorIndex=Binary(errorBlock, currentIteration, shuffles_fromPrev)
			FlipBit(shuffles_fromPrev, shuffles_fromFirst, currentIteration, lastIteration, currentErrorIndex)
		if not errorBlocks:
			break

def CascadeLocalTest(testsNumber=100, keyLengthInBytes=1000, testQber=0.05, iterationsNumber=4, testPing=0):
	correct_keys=0
	wrong_keys=0
	global parity_requests
	parity_requests=0
	print("Processing tests",testsNumber)
	print ("Key length in bits before reconciliation",keyLengthInBytes*8)
	for i in range(testsNumber):
		global correctKey
		global correctKeyFull
		correctKeyFull=RandomBitArray(keyLengthInBytes)
		correctKey=correctKeyFull[correctKeyFull.length()//2:]
		rawKey=AddNoise(testQber)
		start=time.time()
		siftedKey=Cascade('rawKey', iterationsNumber, None, testQber)
		if util.count_xor(siftedKey, correctKey):
			wrong_keys+=1
		else:
			correct_keys+=1
		finish=time.time()
	print("wrong",wrong_keys)
	print("correct",correct_keys)
	print("parity requests in average",round(float(parity_requests)/testsNumber,1))
	print("total time in average",round(parity_requests/testsNumber*2*testPing*0.001+finish-start,1))

CascadeLocalTest()