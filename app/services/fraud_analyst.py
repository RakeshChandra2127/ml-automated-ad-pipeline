import json
import uuid
from typing import Dict, Any, List
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event import FraudReport
from app.services.aggregator import TrafficAggregator
from app.config import get_settings

class FraudAnalystAgent:
    """
    AI-powered fraud detection agent that analyzes traffic patterns and
    generates actionable intelligence reports using LLMs.
    
    The agent:
    1. Queries aggregated traffic data from PostgreSQL
    2. Identifies statistical anomalies (high CTR, IP concentration, timing)
    3. Feeds structured data context to an LLM acting as an AdOps Fraud Analyst
    4. Parses the LLM's structured JSON response
    5. Persists the report to the database
    """
    def __init__(self, settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.aggregator = TrafficAggregator()

    async def analyze(self, db: AsyncSession, window_minutes: int = 60) -> FraudReport:
        # 1. Gather Aggregated Data
        anomaly_candidates = await self.aggregator.get_anomaly_candidates(db, window_minutes)
        top_ips = await self.aggregator.get_top_ips(db, window_minutes)
        total_events = sum([c.get('event_count', 0) for c in anomaly_candidates])
        
        # 2. Build detailed prompt
        window_info = f"Last {window_minutes} minutes"
        prompt = self._build_analysis_prompt(anomaly_candidates, top_ips, total_events, window_info)
        
        # 3. Call LLM
        response = await self.client.chat.completions.create(
            model="gpt-4-turbo-preview",  # Defaulting to an advanced model
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert AdOps Fraud Analyst at a major ad-tech company."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"}
        )
        
        # 4. Parse the LLM's structured JSON response
        llm_output = response.choices[0].message.content
        parsed_data = json.loads(llm_output)
        
        # 5. Persist to DB
        report = FraudReport(
            id=str(uuid.uuid4()),
            risk_level=parsed_data.get('risk_level', 'LOW'),
            suspicious_ips=parsed_data.get('suspicious_ips', []),
            fraud_patterns=parsed_data.get('fraud_patterns', []),
            recommended_actions=parsed_data.get('recommended_actions', [])
        )
        
        db.add(report)
        await db.commit()
        await db.refresh(report)
        
        return report

    def _build_analysis_prompt(self, anomalies: List[Dict], top_ips: List[Dict], total_events: int, window_info: str) -> str:
        return f"""
        Please analyze the following ad traffic data and identify potential fraud.
        
        Time Window: {window_info}
        Total Suspicious Events Flagged by Heuristics: {total_events}
        
        Top IPs Traffic:
        {json.dumps(top_ips, indent=2)}
        
        Anomaly Candidates (High CTR, Time Anomalies, etc.):
        {json.dumps(anomalies, indent=2)}
        
        Output a JSON object with the following schema:
        {{
            "risk_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
            "suspicious_ips": [
                {{
                    "ip": "string",
                    "reason": "string",
                    "confidence": float
                }}
            ],
            "fraud_patterns": ["string"],
            "recommended_actions": ["string"]
        }}
        """
