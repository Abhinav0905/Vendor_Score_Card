from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import models.base as base
import models.supplier as supplier_model
from ml.predictor import SupplierPredictor
from ml.llm_processor import LLMQueryProcessor
from fastapi.middleware.cors import CORSMiddleware

origins = [
   # "http://localhost.tiangolo.com",
   # "https://localhost.tiangolo.com",
   # "http://localhost"
    "http://localhost:3000",
]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
predictor = SupplierPredictor()
llm_processor = LLMQueryProcessor()


def get_db():
    db = base.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/suppliers/")
async def get_suppliers(db: Session = Depends(get_db)):
    return db.query(supplier_model.Supplier).all()


@app.get("/suppliers/{supplier_id}/predict")
async def predict_supplier_risk(supplier_id: str, db: Session = Depends(get_db)):
    supplier = db.query(supplier_model.Supplier).filter_by(id=supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
        
    supplier_data = {
        "data_accuracy": supplier.data_accuracy,
        "error_rate": supplier.error_rate,
        "response_time": supplier.response_time
    }
    
    risk_score = predictor.predict_risk(supplier_data)
    recommendations = predictor.get_recommendations(supplier_data)
    
    return {
        "risk_score": risk_score,
        "recommendations": recommendations
    }


@app.post("/query")
async def process_natural_query(query: str):
    return llm_processor.process_query(query)