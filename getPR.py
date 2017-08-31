# -*- coding: utf-8 -*-

'''
@author: m1tang
'''


import requests
from bs4 import BeautifulSoup as bs
import logging
import sys
import re
import time
import csv
import os
import msvcrt

class UserPara:
    user_name = None
    password = None

class ResultCsv:
    csv_path = "result.csv"
    if os.path.exists(csv_path):
        os.remove(csv_path)
    csv_file = open(csv_path, "w")
    csv_writer = csv.writer(csv_file)
    searched_pr = 0
    captured_pr = 0
    
    @classmethod
    def writeRow(cls, data):
        cls.csv_writer.writerow(data)
        
    @classmethod    
    def close(cls):
        cls.csv_file.close()

def configLogger():
    gLogConf = {
        'filename': 'PRSERACH.log',
        'filemode': 'w',
        'level':    logging.INFO,
        'format':   '%(asctime)s %(levelname)s %(module)s:%(lineno)s : %(message)s',
        'stream':   sys.stdout,
    }
    
    logging.basicConfig(**gLogConf)
   
def getURL(url):
    logging.info("searching url %s" % url)
    login_url = "https://wam.inside.nsn.com/siteminderagent/forms/login.fcc"
    params = {"SMENC":"ISO-8859-1",
          "SMLOCALE":"US-EN",
          "USER":UserPara.user_name,
          "PASSWORD":UserPara.password,
          "target":url,
          "smauthreason": "0",
          "postpreservationdata":""}

    session = requests.session()
    try:
        s = session.post(login_url, params, verify=False)
    except Exception:
        logging.error("get %s page fail" % url)
        logging.error("check: username: %s, password:%s" % (UserPara.user_name, UserPara.password))
        return None
    time.sleep(1)
    return s.text

def getPRSum(page_content):
    if not page_content:
        logging.error("there is no content in the total PR page")
    logging.info("getting the PR sum count")
    bs_obj = bs(page_content)
    count = bs_obj.find("div", {"class":"tablePaging"})
    if not count:
        logging.error("does not find PR sum count")
        return 0
    s = count.get_text()
    try:
        pr_num = s.strip().split(" ")[1].strip()
    except Exception:
        logging.error("parse PR sum count error, the need parsed context is %s" % s)
        return 0
    sum_pr = int(pr_num)
    logging.info("PR sum count is %d" % sum_pr)
    return sum_pr

def getPRLinksPerPage(page_content, page_num):
    logging.info("getting the PRs %d page" % page_num)
    bs_obj = bs(page_content)
    pr_link_list = bs_obj.findAll("a", href=re.compile("\.\/problemReport.html\?prid=.*"))
    if not pr_link_list:
        logging.info("PR page %d has no PR" % page_num)
    return pr_link_list

def mapPRUrl(link_url):
    common_url = "https://pronto.inside.nsn.com/pronto"
    if 'href' in link_url.attrs:
        return common_url + link_url.attrs["href"][1:]
    return None

def getPRUrlListPerPage(pr_link_list):
    return map(mapPRUrl, pr_link_list)

def isFindHZOAMFromHistoryTransfer(ele_history):
    content = ele_history.get_text()
    if "NIHZSSOAM to" in content:
        return True
    return False
    
def isTransferFromHZOAM(pr_selected_page_content, pr_id):
    logging.info("judging the PR %s whether transferred from NIHZSSOAM or not" % pr_id)
    bs_obj = bs(pr_selected_page_content)
    history_comment = bs_obj.findAll("div", {"class":"inputBlock"})
    is_find_hzoam = map(isFindHZOAMFromHistoryTransfer, history_comment)
    isNeedProcess =  any(is_find_hzoam)
    logging.info("the PR %s transferred from NIHZSSOAM: %s" % (pr_id, isNeedProcess))
    return isNeedProcess

def getCorrectionUrl(pr_selected_page_content, pr_id):
    logging.info("getting the PR %s correction url" % pr_id)
    bs_obj = bs(pr_selected_page_content)
    correction_link_list = bs_obj.findAll("a", href=re.compile("\.\/detailCorrection.html\?correctionId=.*"))
    correction_url_list = map(mapPRUrl, correction_link_list)
    return correction_url_list

def isInNeedDomain(tag):
    domains = ["REM", "SWM", "DEM", "MCTRL", "URI", "FRI"]
    content = tag.get_text().strip()
    if content in domains:
        return True
    return False
    
def processCorrectionPage(correction_url):
    cr_page_content = getURL(correction_url)
    if not cr_page_content:
        return False
    bs_obj = bs(cr_page_content)
    tag_list = bs_obj.findAll("span", {"class":"Table_Data1_2"})
    tag_rs = map(isInNeedDomain, tag_list)
    isFind = any(tag_rs)
    return isFind

def findNeedCorrectionDomain(correction_url_list, pr_id):
    rs = map(processCorrectionPage, correction_url_list)
    isFind = any(rs)
    logging.info("the PR %s correction domain in the search domains: %s" % (pr_id, isFind))
    return isFind

def processPRUrl(url):
    pat = ".*prid=([\w\d]*)&.*"
    m = re.match(pat, url)
    if not m:
        logging.error("not find the PR id")
        return
    pr_id = m.group(1)
    ResultCsv.searched_pr += 1
    pr_page = getURL(url)
    if not pr_page:
        return
    rs = isTransferFromHZOAM(pr_page, pr_id)
    if not rs:
        return
    cr_url_list = getCorrectionUrl(pr_page, pr_id)
    isFind = findNeedCorrectionDomain(cr_url_list, pr_id)
    if isFind:
        logging.info("PR %s is found" % pr_id)
        ResultCsv.captured_pr += 1
        ResultCsv.writeRow([pr_id, url])
    
def startCountPR(page_num):
    url = "https://pronto.inside.nsn.com/pronto/fetchReports.html?" +\
        "itemPg=%d" % page_num +\
        "&Sort=state&searchString=&view=All+Problems&viewName=All+Problems&viewName=&status=Closed&startPage=1&sortOrder=Asc&sortField=state&view=All%20Problems&viewName=All%20Problems&viewState=Closed&parentTab=pr_report_list"
    items_page = getURL(url)
    if not items_page:
        return
    page_links = getPRLinksPerPage(items_page, page_num)
    pronto_urls = getPRUrlListPerPage(page_links)
    map(processPRUrl, pronto_urls)

def testSingleUrl():
    url = "https://pronto.inside.nsn.com/pronto/problemReport.html?prid=PR272288&status=Closed&startPage=1&sortOrder=Asc&sortField=state&view=All%20Problems&viewName=All%20Problems&viewState=Closed&parentTab=pr_report_list"
    processPRUrl(url)

def pwdInput(msg):  
    if msg:  
        sys.stdout.write(msg)  
    chars = []  
    while True:  
        newChar = msvcrt.getch()  
        if newChar in '\3\r\n': # 如果是换行，Ctrl+C，则输入结束  
            if newChar in '\3': # 如果是Ctrl+C，则将输入清空，返回空字符串  
                chars = []  
            break  
        elif newChar == '\b': # 如果是退格，则删除末尾一位  
            if chars:  
                del chars[-1]  
                sys.stdout.write('\b \b') # 左移一位，用空格抹掉星号，再退格  
        else:  
            chars.append(newChar)  
            sys.stdout.write('*') # 显示为星号  
    sys.stdout.write('\n')
    return ''.join(chars)  

def getUserPara():
    user_name = raw_input("please input your user name:\n")
    password = pwdInput("please input your password:\n")
    pages = raw_input("please input how many pages you want to search(default is all pages):\n")
    return user_name, password, pages
    
if __name__ == "__main__":
    UserPara.user_name, UserPara.password, pages = getUserPara()
    if not UserPara.user_name or not UserPara.password:
        print "username or password is null, please try again"
        exit(1)
    
    configLogger()
    if not pages:
        url = "https://pronto.inside.nsn.com/pronto/fetchReports.html?itemPg=1&Sort=state&searchString=&view=All+Problems&viewName=All+Problems&viewName=&status=Closed&startPage=1&sortOrder=Asc&sortField=state&view=All%20Problems&viewName=All%20Problems&viewState=Closed&parentTab=pr_report_list"
        pr_count_sum = getPRSum(getURL(url))
        pages = pr_count_sum / 20
        if pr_count_sum % 20:
            pages += 1
    else:
        try:
            pages = int(pages)
        except Exception as e:
            print e
            print "input page number is not right"
            exit(1)
            
    map(startCountPR, range(1, pages+1))
    ResultCsv.writeRow(["Search total PR: %d" % ResultCsv.searched_pr, "captured PR: %d" % ResultCsv.captured_pr])
    ResultCsv.close()
    logging.info("Search total PR: %d, captured PR: %d" % (ResultCsv.searched_pr, ResultCsv.captured_pr))
    print "Search total PR: %d, captured PR: %d" % (ResultCsv.searched_pr, ResultCsv.captured_pr)
    raw_input()
    