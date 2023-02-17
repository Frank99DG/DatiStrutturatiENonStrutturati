from bs4 import BeautifulSoup
import requests
import re
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

def find_name(link):
    r = requests.get(link, headers = headers)
    soup = BeautifulSoup(r.content, features = 'html.parser')
    #pattern = r' Generic Name\(S\): (\w*) '
    for tag in soup.find_all("h1", class_="drug-name"):
        #if re.search(pattern, tag.string):
            #return re.search(pattern, tag.string).group(1)
        print(tag.contents[0].strip())

if __name__=="__main__":
    symptons = []
    with open("DatiStrutturatiENonStrutturati\dict_start.txt", "r") as text:
        for line in text.readlines():
            symptons.append(line.strip())
    print(symptons)