"""Synthetic MAVIS backend for isolated native tests only."""
import sys
source=sys.argv[1]
while True:
 d={}
 for line in sys.stdin:
  line=line.rstrip('\n')
  if line=='=':break
  key,value=line.split(' ',1);d[int(key)]=value
 else:break
 user=d.get(4,'');code=0
 if source=='bound' and user=='third':d[6]='NFD';code=16
 else:
  d[6]='ACK'
  if user in ('external','third'):d[47]='"ops"'
  if user=='nonmember':d[47]='"other"'
 d.pop(8,None)
 for key,value in d.items():print(key,value)
 print('='+str(code),flush=True)
