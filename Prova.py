from bs4 import BeautifulSoup
from urllib.request import urlopen
html = urlopen("file:///C:/Users/domi0/Desktop/index.html") #collegamneto alla pagina tramite url
soup = BeautifulSoup(html, features = "html.parser") #legge la pagina


#attento che la find_all conta come elementi anche i semplici \n che invece non sono tag :c
        
        
def children(soup, i = 1, j = 0):
    tags = list(soup.find_all(recursive = False))
    tags = [tag for tag in tags if tag != "\n"]
    k = len(tags)
    if k == 0: return []
    for child in tags:
        print("i = {0}, j = {1}, child = \n{2}\n\n".format(i, j, child))
        children(child, i + k, i)
        k -= 1
        

children(soup)