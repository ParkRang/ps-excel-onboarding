from fastapi import FastAPI
from db.database import Base, engine
from job.job import Job
from order.order import Order
from job.job_router import router as job_router
from excel.excel_router import router as excel_router
from fastapi.middleware.cors import CORSMiddleware

import os
import json
from dotenv import load_dotenv
from google.cloud import tasks_v2

from core.logging import setup_logger

setup_logger()

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(job_router)
app.include_router(excel_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    # push_test_task()
    return {"message": "Hello from FastAPI backend!"}


load_dotenv()

def push_test_task():
    # 코드 내부에 API 키를 직접 적지 않아도 알아서 컴퓨터 안의 인증 열쇠를 찾아 연결합니다!
    client = tasks_v2.CloudTasksClient()
    
    queue_path = client.queue_path(
        os.getenv("GCP_PROJECT_ID"), 
        os.getenv("GCP_QUEUE_LOCATION"), 
        os.getenv("GCP_QUEUE_NAME")
    )
    
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": "https://httpbin.org",  # 테스트용 임시 가상 주소
            "headers": {"Content-type": "application/json"},
            "body": json.dumps({"text": "Hello Google Tasks!"}).encode()
        }
    }
    
    response = client.create_task(request={"parent": queue_path, "task": task})
    print(f"🚀 [성공] 구글 큐에 대기 작업 안착! 태스크 ID: {response.name}")