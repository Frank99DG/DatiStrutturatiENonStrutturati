
from bs4 import BeautifulSoup
from urllib.request import urlopen
html = urlopen("file:///C:/Users/dgfra/Downloads/index.html") #collegamneto alla pagina tramite url
Obj = BeautifulSoup(html.read()) #legge la pagina

for tag in Obj.find_all(True):
    if tag.name=='head':
        for val in tag.contents:
            if val.name!=None:
                print(val.name) 


