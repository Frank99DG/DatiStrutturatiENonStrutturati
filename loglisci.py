from bs4 import BeautifulSoup
import requests

url = 'https://www.webmd.com/drugs/drugreview-5310-hydrochlorothiazide-oral?conditionid=&sortval=1&page='
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

r = requests.get(url, headers = headers)
soup = BeautifulSoup(r.content, features= 'html.parser')

reviews_container = soup.find("div", class_ = "shared-reviews-container")
lastpage = reviews_container.find_all('a',class_="page-link")[-1].string.strip()
print(lastpage)

# Non vengono prese per intero alcune recensioni (read more)
reviews_soup = reviews_container.find_all("div", class_ = "review-details-holder") # Questi sono i contenitori delle recensioni
#print(reviews_soup)

for review in reviews_soup:

    #print('NEW USER')
    user_data = review.find("div", class_ = 'details').find_all('span')
    (name, age, sex, kind) = (data.string.replace('|', '').strip() for data in user_data)
    #print(name, age, sex, kind)

    condition = review.find("strong", class_ = 'condition').string.lstrip('Condition: ')
    #print(condition)
    
    node = review.find_all("p", class_ = 'description-text')
    #print(node, '\n')
    if len(list(node[0].children)) == 1 : text = node[0].string # len(list(...))
    else:
        shown_text = node[0].find("span", class_="showSec")
        hidden_text = node[0].find("span", class_="hiddenSec")
        text = shown_text.string + hidden_text.string
    #print(text, '\n\n')
        
