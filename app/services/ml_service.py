import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.expense import Expense
from app.models.attendance import Attendance
from app.models.project import Project
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import logging
import pickle
import os

logger = logging.getLogger(__name__)

class MLService:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.model_dir = "ml_models"
        os.makedirs(self.model_dir, exist_ok=True)

    def prepare_expense_data(self, db: Session, organization_id: int, days_back: int = 365) -> pd.DataFrame:
        """Prepare expense data for ML training"""
        try:
            # Get expenses from the last N days
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            expenses = db.query(Expense).filter(
                Expense.organization_id == organization_id,
                Expense.expense_date >= cutoff_date
            ).all()
            
            if not expenses:
                logger.warning(f"No expenses found for org {organization_id} in last {days_back} days")
                return pd.DataFrame()
            
            # Convert to DataFrame
            data = []
            for expense in expenses:
                data.append({
                    'date': expense.expense_date,
                    'amount': float(expense.amount),
                    'category': expense.category or 'other',
                    'description': expense.description or '',
                    'project_id': expense.project_id,
                    'user_id': expense.user_id
                })
            
            df = pd.DataFrame(data)
            
            # Feature engineering
            df['day_of_week'] = df['date'].dt.dayofweek
            df['day_of_month'] = df['date'].dt.day
            df['month'] = df['date'].dt.month
            df['quarter'] = df['date'].dt.quarter
            df['week_of_year'] = df['date'].dt.isocalendar().week
            df['day_of_year'] = df['date'].dt.dayofyear
            
            # Category encoding
            df['category_encoded'] = pd.Categorical(df['category']).codes
            
            # Rolling averages
            df = df.sort_values('date')
            df['amount_7d_avg'] = df['amount'].rolling(window=7, min_periods=1).mean()
            df['amount_30d_avg'] = df['amount'].rolling(window=30, min_periods=1).mean()
            
            # Lag features
            df['amount_lag_1'] = df['amount'].shift(1)
            df['amount_lag_7'] = df['amount'].shift(7)
            
            # Fill NaN values
            df = df.fillna(method='bfill').fillna(0)
            
            return df
            
        except Exception as e:
            logger.error(f"Error preparing expense data: {e}")
            return pd.DataFrame()

    def prepare_attendance_data(self, db: Session, organization_id: int, days_back: int = 365) -> pd.DataFrame:
        """Prepare attendance data for ML training"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            attendances = db.query(Attendance).filter(
                Attendance.organization_id == organization_id,
                Attendance.check_in >= cutoff_date
            ).all()
            
            if not attendances:
                return pd.DataFrame()
            
            data = []
            for attendance in attendances:
                data.append({
                    'date': attendance.check_in,
                    'hours_worked': float(attendance.hours_worked or 0),
                    'user_id': attendance.user_id
                })
            
            df = pd.DataFrame(data)
            
            # Feature engineering
            df['day_of_week'] = df['date'].dt.dayofweek
            df['day_of_month'] = df['date'].dt.day
            df['month'] = df['date'].dt.month
            df['quarter'] = df['date'].dt.quarter
            df['week_of_year'] = df['date'].dt.isocalendar().week
            
            # Rolling averages
            df = df.sort_values('date')
            df['hours_7d_avg'] = df['hours_worked'].rolling(window=7, min_periods=1).mean()
            df['hours_30d_avg'] = df['hours_worked'].rolling(window=30, min_periods=1).mean()
            
            # Lag features
            df['hours_lag_1'] = df['hours_worked'].shift(1)
            df['hours_lag_7'] = df['hours_worked'].shift(7)
            
            # Fill NaN values
            df = df.fillna(method='bfill').fillna(0)
            
            return df
            
        except Exception as e:
            logger.error(f"Error preparing attendance data: {e}")
            return pd.DataFrame()

    def train_expense_prediction_model(self, db: Session, organization_id: int) -> Dict:
        """Train expense prediction model"""
        try:
            # Prepare data
            df = self.prepare_expense_data(db, organization_id)
            
            if df.empty or len(df) < 30:
                return {
                    "success": False,
                    "error": "Insufficient data for training (minimum 30 records required)"
                }
            
            # Select features
            feature_columns = [
                'day_of_week', 'day_of_month', 'month', 'quarter', 
                'week_of_year', 'category_encoded', 'amount_7d_avg', 
                'amount_30d_avg', 'amount_lag_1', 'amount_lag_7'
            ]
            
            X = df[feature_columns]
            y = df['amount']
            
            # Split data
            split_point = int(len(X) * 0.8)
            X_train, X_test = X[:split_point], X[split_point:]
            y_train, y_test = y[:split_point], y[split_point:]
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train models
            models = {
                'linear': LinearRegression(),
                'random_forest': RandomForestRegressor(n_estimators=100, random_state=42)
            }
            
            results = {}
            
            for name, model in models.items():
                # Train
                if name == 'linear':
                    model.fit(X_train_scaled, y_train)
                else:
                    model.fit(X_train, y_train)
                
                # Predict
                if name == 'linear':
                    y_pred = model.predict(X_test_scaled)
                else:
                    y_pred = model.predict(X_test)
                
                # Evaluate
                mae = mean_absolute_error(y_test, y_pred)
                mse = mean_squared_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)
                
                results[name] = {
                    'mae': mae,
                    'mse': mse,
                    'r2': r2,
                    'model': model,
                    'scaler': scaler if name == 'linear' else None
                }
            
            # Select best model
            best_model_name = min(results.keys(), key=lambda x: results[x]['mae'])
            best_model = results[best_model_name]
            
            # Save model
            model_path = os.path.join(self.model_dir, f"expense_model_org_{organization_id}.pkl")
            scaler_path = os.path.join(self.model_dir, f"expense_scaler_org_{organization_id}.pkl")
            
            with open(model_path, 'wb') as f:
                pickle.dump(best_model['model'], f)
            
            if best_model['scaler']:
                with open(scaler_path, 'wb') as f:
                    pickle.dump(best_model['scaler'], f)
            
            # Store in memory
            self.models[f"expense_{organization_id}"] = best_model['model']
            self.scalers[f"expense_{organization_id}"] = best_model['scaler']
            
            return {
                "success": True,
                "model_type": best_model_name,
                "mae": best_model['mae'],
                "mse": best_model['mse'],
                "r2": best_model['r2'],
                "training_samples": len(X_train),
                "test_samples": len(X_test)
            }
            
        except Exception as e:
            logger.error(f"Error training expense model: {e}")
            return {"success": False, "error": str(e)}

    def predict_expenses(self, db: Session, organization_id: int, days_ahead: int = 30) -> Dict:
        """Predict expenses for the next N days"""
        try:
            # Load model
            model_key = f"expense_{organization_id}"
            
            if model_key not in self.models:
                # Try to load from disk
                model_path = os.path.join(self.model_dir, f"expense_model_org_{organization_id}.pkl")
                if os.path.exists(model_path):
                    with open(model_path, 'rb') as f:
                        self.models[model_key] = pickle.load(f)
                    
                    scaler_path = os.path.join(self.model_dir, f"expense_scaler_org_{organization_id}.pkl")
                    if os.path.exists(scaler_path):
                        with open(scaler_path, 'rb') as f:
                            self.scalers[model_key] = pickle.load(f)
                else:
                    return {
                        "success": False,
                        "error": "No trained model found. Please train the model first."
                    }
            
            # Get recent data for prediction
            df = self.prepare_expense_data(db, organization_id, days_back=60)
            
            if df.empty:
                return {"success": False, "error": "No recent data available for prediction"}
            
            # Prepare future dates
            future_dates = []
            current_date = datetime.now().date()
            
            for i in range(days_ahead):
                future_date = current_date + timedelta(days=i+1)
                future_dates.append(future_date)
            
            # Create features for future dates
            predictions = []
            
            for date in future_dates:
                # Use the most recent features as base
                latest_features = df.iloc[-1].copy()
                
                # Update date features
                latest_features['date'] = datetime.combine(date, datetime.min.time())
                latest_features['day_of_week'] = date.weekday()
                latest_features['day_of_month'] = date.day
                latest_features['month'] = date.month
                latest_features['quarter'] = (date.month - 1) // 3 + 1
                latest_features['week_of_year'] = date.isocalendar()[1]
                latest_features['day_of_year'] = date.timetuple().tm_yday
                
                # Prepare feature vector
                feature_vector = np.array([[
                    latest_features['day_of_week'],
                    latest_features['day_of_month'],
                    latest_features['month'],
                    latest_features['quarter'],
                    latest_features['week_of_year'],
                    latest_features['category_encoded'],
                    latest_features['amount_7d_avg'],
                    latest_features['amount_30d_avg'],
                    latest_features['amount_lag_1'],
                    latest_features['amount_lag_7']
                ]])
                
                # Predict
                model = self.models[model_key]
                scaler = self.scalers.get(model_key)
                
                if scaler:
                    feature_vector = scaler.transform(feature_vector)
                
                prediction = model.predict(feature_vector)[0]
                predictions.append({
                    'date': date.isoformat(),
                    'predicted_amount': max(0, prediction)  # Ensure non-negative
                })
            
            # Calculate statistics
            total_predicted = sum(p['predicted_amount'] for p in predictions)
            daily_average = total_predicted / len(predictions)
            
            return {
                "success": True,
                "predictions": predictions,
                "summary": {
                    "total_predicted": total_predicted,
                    "daily_average": daily_average,
                    "prediction_period": f"{days_ahead} days",
                    "currency": "ARS"
                }
            }
            
        except Exception as e:
            logger.error(f"Error predicting expenses: {e}")
            return {"success": False, "error": str(e)}

    def get_historical_trends(self, db: Session, organization_id: int, days_back: int = 180) -> Dict:
        """Analyze historical trends and patterns"""
        try:
            # Get expense data
            expense_df = self.prepare_expense_data(db, organization_id, days_back)
            
            if expense_df.empty:
                return {"success": False, "error": "No historical data available"}
            
            logger.info(f"Processing {len(expense_df)} expense records for trends")
            
            # Get attendance data
            attendance_df = self.prepare_attendance_data(db, organization_id, days_back)
            
            # Analyze trends
            trends = {}
            
            # Expense trends
            expense_df['date'] = pd.to_datetime(expense_df['date'])
            daily_expenses = expense_df.groupby(expense_df['date'].dt.date)['amount'].sum()
            
            # Calculate moving averages
            ma_7d = daily_expenses.rolling(window=7).mean()
            ma_30d = daily_expenses.rolling(window=30).mean()
            
            # Category trends
            category_trends = expense_df.groupby('category')['amount'].agg(['sum', 'count', 'mean'])
            
            # Monthly trends
            monthly_expenses = expense_df.groupby(expense_df['date'].dt.to_period('M'))['amount'].sum()
            
            # Convertir a formato JSON-serializable
            trends['expenses'] = {
                'daily_total': {str(k): float(v) for k, v in daily_expenses.to_dict().items()},
                'moving_average_7d': {str(k): float(v) if pd.notna(v) else 0 for k, v in ma_7d.to_dict().items()},
                'moving_average_30d': {str(k): float(v) if pd.notna(v) else 0 for k, v in ma_30d.to_dict().items()},
                'category_breakdown': {
                    cat: {
                        'sum': float(row['sum']),
                        'count': int(row['count']),
                        'mean': float(row['mean'])
                    } for cat, row in category_trends.iterrows()
                },
                'monthly_totals': {str(k): float(v) for k, v in monthly_expenses.to_dict().items()},
                'total_period': float(daily_expenses.sum()),
                'average_daily': float(daily_expenses.mean()),
                'growth_rate': float(self._calculate_growth_rate(daily_expenses))
            }
            
            # Attendance trends (if available)
            if not attendance_df.empty:
                attendance_df['date'] = pd.to_datetime(attendance_df['date'])
                daily_hours = attendance_df.groupby(attendance_df['date'].dt.date)['hours_worked'].sum()
                
                trends['attendance'] = {
                    'daily_hours': {str(k): float(v) for k, v in daily_hours.to_dict().items()},
                    'average_daily_hours': float(daily_hours.mean()),
                    'total_hours': float(daily_hours.sum())
                }
            
            # Correlation analysis
            if not attendance_df.empty and not expense_df.empty:
                # Merge data for correlation
                daily_data = pd.DataFrame({
                    'expenses': daily_expenses,
                    'hours': daily_hours
                }).dropna()
                
                correlation = daily_data['expenses'].corr(daily_data['hours'])
                trends['correlations'] = {
                    'expense_hours_correlation': correlation
                }
            
            return {
                "success": True,
                "trends": trends,
                "analysis_period": f"{days_back} days",
                "data_points": len(daily_expenses)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {"success": False, "error": str(e)}

    def get_project_profitability(self, db: Session, organization_id: int) -> Dict:
        """Analyze profitability by project"""
        try:
            # Get all projects with expenses
            projects = db.query(Project).filter(
                Project.organization_id == organization_id
            ).all()
            
            profitability_data = []
            
            for project in projects:
                # Get project expenses
                expenses = db.query(Expense).filter(
                    Expense.organization_id == organization_id,
                    Expense.project_id == project.id
                ).all()
                
                total_expenses = sum(exp.amount for exp in expenses)
                expense_count = len(expenses)
                
                # Get project attendance (hours worked)
                # Simplified: estimate hours based on project expenses and activity
                # In real implementation you'd track hours per project
                if expense_count > 0:
                    # Estimate hours based on expense frequency and project complexity
                    estimated_hours = expense_count * 8  # Assume 8 hours per expense transaction
                    # Cap at reasonable maximum (e.g., 160 hours per month per project)
                    estimated_hours = min(estimated_hours, 160)
                else:
                    estimated_hours = 0
                
                # Calculate profitability metrics
                estimated_hourly_cost = total_expenses / max(estimated_hours, 1)
                
                profitability_data.append({
                    'project_id': project.id,
                    'project_name': project.name,
                    'total_expenses': total_expenses,
                    'expense_count': expense_count,
                    'estimated_hours_worked': estimated_hours,
                    'estimated_hourly_cost': estimated_hourly_cost,
                    'efficiency_score': max(0, 100 - (estimated_hourly_cost / 100))  # Simplified
                })
            
            # Sort by efficiency
            profitability_data.sort(key=lambda x: x['efficiency_score'], reverse=True)
            
            # Calculate summary statistics
            if profitability_data:
                avg_expenses = sum(p['total_expenses'] for p in profitability_data) / len(profitability_data)
                avg_efficiency = sum(p['efficiency_score'] for p in profitability_data) / len(profitability_data)
            else:
                avg_expenses = 0
                avg_efficiency = 0
            
            return {
                "success": True,
                "projects": profitability_data,
                "summary": {
                    "total_projects": len(profitability_data),
                    "average_expenses_per_project": avg_expenses,
                    "average_efficiency_score": avg_efficiency
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing project profitability: {e}")
            return {"success": False, "error": str(e)}

    def _calculate_growth_rate(self, series: pd.Series) -> float:
        """Calculate growth rate from time series"""
        try:
            if len(series) < 2:
                return 0.0
            
            # Simple linear regression for trend
            x = np.arange(len(series))
            y = series.values
            
            # Remove NaN values
            mask = ~np.isnan(y)
            x = x[mask]
            y = y[mask]
            
            if len(x) < 2:
                return 0.0
            
            # Calculate slope (growth rate)
            slope = np.polyfit(x, y, 1)[0]
            
            # Normalize by average value
            avg_value = np.mean(y)
            growth_rate = (slope / avg_value) * 100 if avg_value != 0 else 0
            
            return growth_rate
            
        except Exception as e:
            logger.error(f"Error calculating growth rate: {e}")
            return 0.0

# Global ML service instance
ml_service = MLService()
