import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import shutil
import time
from google.generativeai.client import configure
from google.generativeai.generative_models import GenerativeModel
import re
import sys


# PubMed api: https://www.ncbi.nlm.nih.gov/books/NBK25497/


def search_pubmed_pmids(keywords_list, journals_list, retmax=20):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    
    # 构建关键词查询
    keyword_terms = []
    for keyword in keywords_list:
        keyword_terms.append(f"{keyword}[Title/Abstract]")
    keyword_query = " OR ".join(keyword_terms)
    
    # 构建期刊查询，处理特殊字符
    journal_terms = []
    for journal in journals_list:
        # 将 & 替换为 AND，并确保期刊名称被正确引用
        journal_name = journal.replace('&', 'AND')
        journal_terms.append(f'"{journal_name}"[Journal]')
    journal_query = " OR ".join(journal_terms)
    
    # 组合查询
    term = f"({keyword_query}) AND ({journal_query})"
    
    params = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "retmax": retmax
    }
    print(f"Search query: {term}")  # 添加调试信息
    resp = requests.get(base_url, params=params)
    data = resp.json()
    return data["esearchresult"]["idlist"]

def fetch_pubmed_details(pmids):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml"
    }
    resp = requests.get(base_url, params=params)
    return resp.text  # 返回XML字符串

def format_zh_abstract(zh):
    def repl(match):
        return f"<b>{match.group(1)}:</b>"
    lines = zh.splitlines()
    lines = [re.sub(r'^([\u4e00-\u9fa5A-Za-z]+):', repl, line) for line in lines]
    return "<br>".join(lines)

def verify_gemini_api_key(api_key):
    """验证 Gemini API key 是否有效"""
    try:
        # 配置 API key
        configure(api_key=api_key)
        # 创建模型实例
        model = GenerativeModel('gemini-2.0-flash')  # 使用 gemini-2.0-flash 模型
        # 尝试一个简单的生成请求
        response = model.generate_content("Hello")
        return True
    except Exception as e:
        print(f"Gemini API key 验证失败: {str(e)}")
        return False

def gemini_translate_and_summarize(text, api_key):
    """使用 Gemini API 翻译和总结文本"""
    try:
        # 配置 API key
        configure(api_key=api_key)
        # 创建模型实例
        model = GenerativeModel('gemini-2.0-flash')  # 使用 gemini-2.0-flash 模型
        prompt = (
            "请将以下英文科技论文摘要翻译成简体中文，要求准确、专业、流畅。"
            "然后对该摘要进行简明扼要的总结（不限定字数），总结内容请放在【总结】后面。\n\n"
            f"英文摘要：\n{text}"
        )
        response = model.generate_content(prompt)
        reply = response.text
        if "【总结】" in reply:
            zh, summary = reply.split("【总结】", 1)
            zh = zh.strip()
            summary = summary.strip()
            zh = format_zh_abstract(zh)
            return zh, summary
        else:
            zh = reply.strip()
            zh = format_zh_abstract(zh)
            return zh, ""
    except Exception as e:
        print("Gemini API 错误:", e)
        return "", ""

def parse_pubmed_xml(xml_text):
    soup = BeautifulSoup(xml_text, "xml")
    papers = []
    api_key = os.getenv('GEMINI_API_KEY')
    
    for article in soup.find_all("PubmedArticle"):
        title = article.ArticleTitle.text if article.ArticleTitle else ""
        abstract = ""
        if article.Abstract:
            abstract_texts = article.Abstract.find_all("AbstractText")
            if abstract_texts:
                parts = []
                for ab in abstract_texts:
                    label = ab.get("Label")
                    part_text = ab.text.strip()
                    if label:
                        parts.append(f"{label}: {part_text}")
                    else:
                        parts.append(part_text)
                abstract = "\n".join(parts)
        abstract_zh = ""
        summary_zh = ""
        if api_key and abstract:
            abstract_zh, summary_zh = gemini_translate_and_summarize(abstract, api_key)
        authors = []
        for author in article.find_all("Author"):
            lastname = author.LastName.text if author.LastName else ""
            firstname = author.ForeName.text if author.ForeName else ""
            if lastname or firstname:
                authors.append(f"{firstname} {lastname}".strip())
        journal = article.Journal.Title.text if article.Journal and article.Journal.Title else ""
        pubdate = ""
        if article.Journal and article.Journal.Issue and article.Journal.Issue.PubDate:
            year = article.Journal.Issue.PubDate.Year
            medline = article.Journal.Issue.PubDate.MedlineDate
            pubdate = year.text if year else (medline.text if medline else "")
        doi = ""
        for id_elem in article.find_all("ArticleId"):
            if id_elem.get("IdType", "").lower() == "doi":
                doi = id_elem.text.strip()
                break
        link = f"https://doi.org/{doi}" if doi else ""
        papers.append({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "abstract_zh": abstract_zh,
            "summary_zh": summary_zh,
            "journal": journal,
            "pubdate": pubdate,
            "doi": doi,
            "link": link
        })
    return papers

def save_papers(papers, output_dir='papers'):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(output_dir, f'papers_{timestamp}.json')
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    # 保存一份为 latest.json
    shutil.copy(filename, os.path.join(output_dir, 'latest.json'))
    return filename

if __name__ == "__main__":
    # 验证 Gemini API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("错误: 未设置 GEMINI_API_KEY 环境变量")
        sys.exit(1)
    
    if not verify_gemini_api_key(api_key):
        print("错误: GEMINI_API_KEY 无效或无法使用")
        sys.exit(1)
    
    print("Gemini API key 验证成功")
    
    # 从环境变量获取关键词和期刊列表，用逗号分隔
    # 如果环境变量未设置，使用默认列表
    default_keywords = ['PET']
    default_journals = ['Medical Physics', 'Physics in Medicine & Biology']
    
    env_keywords = os.getenv('SEARCH_KEYWORDS')
    env_journals = os.getenv('JOURNAL_NAME')
    
    # 如果环境变量存在，则分割字符串为列表
    keywords = env_keywords.split(',') if env_keywords else default_keywords
    journals = env_journals.split(',') if env_journals else default_journals
    
    # 去除空白字符
    keywords = [k.strip() for k in keywords]
    journals = [j.strip() for j in journals]
    
    print(f"Searching PubMed for keywords: {keywords}")
    print(f"In journals: {journals}")
    
    pmids = search_pubmed_pmids(keywords, journals)
    if pmids:
        xml_text = fetch_pubmed_details(pmids)
        papers = parse_pubmed_xml(xml_text)
        if papers:
            output_file = save_papers(papers)
            print(f"Papers saved to {output_file}")
        else:
            print("No papers found")
    else:
        print("No papers found") 