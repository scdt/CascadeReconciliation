import socket
import CascadeReconciliation as rec
import bitarray

HOST='localhost'
PORT=9090

rawkey_filename='rawkey'
iterationsNumber=4
knownQBER=None

sock=socket.socket()
sock.connect((HOST,PORT))
print 'Connected'

try:
	siftedkey=rec.Cascade(rawkey_filename, iterationsNumber, sock, knownQBER)
	print 'Key sifted'
	sock.send()
	bobHash=hash(frozenbitarray(siftedkey))
	sock.send('Key sifted')sock.send(bobHash)
	result=sock.recv(64)
	if result.decode('utf-8')=='Key reconciled':
		print 'Key reconciled'
	else:
		print 'Reconciliation failed'
except Exception as e:
	print(e)
	sock.close()
else:
	sock.close()