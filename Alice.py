import socket
import bitarray
import CascadeReconciliation as rec

PORT=9090
correctkey_filename='correctkey'

def GetParity(indexes, key):
	bits=bitarray([key[i] for i in indexes])
	return bits.count(True)%2

correctkey=rec.GetBitArray(correctkey_filename)

sock=socket.socket()
sock.bind(('',PORT))
sock.listen(1)
conn,addr=sock.accept()
print 'Connected', addr

try:
	data=conn.recv(64)
	if data.decode('utf-8')=='Cascade qber estimation':
		conn.sendall(tobytes(correctkey[:correctkey.length()/2]))
		correctkey=correctkey[correctkey.length()/2:]
	while True:
		data=conn.recv(4096)
		if not data:
			break
		indexes=pickle.loads(data)
		parity=GetParity(indexes, correctkey)
		conn.send(parity)
	aliceHash=hash(frozenbitarray(correctkey))
	bobHash=int.from_bytes(conn.recv(64))
	if aliceHash==bobHash:
		conn.sendall(b'Key reconciled')
except Exception as e:
	print(e)
	conn.close()
else:
	conn.close()