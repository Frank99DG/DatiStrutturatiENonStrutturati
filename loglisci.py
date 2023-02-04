from bs4 import BeautifulSoup
from urllib.request import urlopen

url = 'https://www.webmd.com/drugs/drugreview-5310-hydrochlorothiazide-oral?conditionid=&sortval=1&page='

soup = BeautifulSoup(url)
html = urlopen(
