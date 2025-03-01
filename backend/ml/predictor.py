import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from typing import List, Dict

class SupplierPredictor:
    def __init__(self):
        self.model = RandomForestRegressor()
        self.scaler = StandardScaler()
        
    def prepare_features(self, data: pd.DataFrame) -> np.ndarray:
        features = ['data_accuracy', 'error_rate', 'response_time']
        X = data[features]
        return self.scaler.fit_transform(X)
        
    def train(self, historical_data: pd.DataFrame):
        X = self.prepare_features(historical_data)
        y = historical_data['compliance_score']
        self.model.fit(X, y)
        
    def predict_risk(self, supplier_data: Dict) -> float:
        features = pd.DataFrame([supplier_data])
        X = self.prepare_features(features)
        return self.model.predict(X)[0]
        
    def get_recommendations(self, supplier_data: Dict) -> List[Dict]:
        risk_score = self.predict_risk(supplier_data)
        recommendations = []
        
        if risk_score > 0.7:
            recommendations.append({
                "type": "critical",
                "message": "High risk of compliance issues detected",
                "action": "Immediate review of data submission process required"
            })
        elif supplier_data['error_rate'] > 5:
            recommendations.append({
                "type": "warning",
                "message": "Elevated error rate detected",
                "action": "Schedule supplier training session"
            })
            
        return recommendations