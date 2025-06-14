import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import shutil
import time

def search_pubmed_pmids(keywords, journal, retmax=10):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{keywords}[Title/Abstract] AND {journal}[Journal]",
        "retmode": "json",
        "retmax": retmax
    }
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

def parse_pubmed_xml(xml_text):
    soup = BeautifulSoup(xml_text, "xml")
    papers = []
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
    keywords = os.getenv('SEARCH_KEYWORDS', 'machine learning')
    journal_name = os.getenv('JOURNAL_NAME', 'Nature')
    print(f"Searching PubMed for: {keywords} in {journal_name}")
    pmids = search_pubmed_pmids(keywords, journal_name)
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