import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time

def search_papers(keywords, journal_name):
    """
    使用关键词和期刊名称搜索论文
    """
    # 这里使用 arXiv API 作为示例
    base_url = "http://export.arxiv.org/api/query"
    
    # 构建查询参数
    search_query = f"all:{keywords}+AND+journal:{journal_name}"
    params = {
        'search_query': search_query,
        'start': 0,
        'max_results': 10,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }
    
    try:
        response = requests.get(base_url, params=params)
        soup = BeautifulSoup(response.content, 'xml')
        
        papers = []
        for entry in soup.find_all('entry'):
            paper = {
                'title': entry.title.text,
                'authors': [author.find('name').text for author in entry.find_all('author')],
                'abstract': entry.summary.text,
                'published': entry.published.text,
                'link': entry.link['href'],
                'pdf_link': entry.link['href'].replace('abs', 'pdf')
            }
            papers.append(paper)
        
        return papers
    except Exception as e:
        print(f"Error fetching papers: {str(e)}")
        return []

def save_papers(papers, output_dir='papers'):
    """
    将论文信息保存为JSON文件
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(output_dir, f'papers_{timestamp}.json')
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    
    return filename

if __name__ == "__main__":
    # 示例使用
    keywords = os.getenv('SEARCH_KEYWORDS', 'machine learning')
    journal_name = os.getenv('JOURNAL_NAME', 'Nature')
    
    papers = search_papers(keywords, journal_name)
    if papers:
        output_file = save_papers(papers)
        print(f"Papers saved to {output_file}")
    else:
        print("No papers found") 