import json
import os
import boto3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from openai import OpenAI
from textblob import TextBlob
import re
from collections import Counter
from agents import Agent, Runner, function_tool
from pydantic import BaseModel


# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource('dynamodb')
state_table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

# OpenAI client
openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])


# Predefined topics for categorization
PREDEFINED_TOPICS = [
    "Product Quality", "Delivery", "Customer Support", "Pricing", 
    "Website/App", "Billing", "Returns", "Shipping", "User Experience"
]

# Pydantic models for strict schema compliance
class EnhancedSentimentAnalysis(BaseModel):
    sentiment: str
    confidence: float
    emotional_indicators: List[str]
    sentiment_reasoning: str

class SentimentAnalysisResult(BaseModel):
    tool_name: str
    basic_sentiment: str
    polarity_score: float
    subjectivity_score: float
    enhanced_analysis: Optional[EnhancedSentimentAnalysis] = None
    error: Optional[str] = None

class TopicAnalysis(BaseModel):
    primary_topic: str
    secondary_topics: List[str]
    topic_scores: Dict[str, float]
    reasoning: str

class TopicCategorizationResult(BaseModel):
    tool_name: str
    available_topics: List[str]
    analysis: Optional[TopicAnalysis] = None
    primary_topic: Optional[str] = None
    error: Optional[str] = None

class KeywordInfo(BaseModel):
    keyword: str
    relevance_score: float
    context: str
    category: str

class EnhancedKeywordAnalysis(BaseModel):
    keywords: List[KeywordInfo]
    key_phrases: List[str]
    entities: List[str]

class KeywordContextualizationResult(BaseModel):
    tool_name: str
    word_frequency: Dict[str, int]
    enhanced_analysis: Optional[EnhancedKeywordAnalysis] = None
    keywords: Optional[List[str]] = None
    error: Optional[str] = None

class ActionableRecommendation(BaseModel):
    action: str
    priority: str
    department: str
    timeline: str

class SummaryAnalysis(BaseModel):
    executive_summary: str
    key_points: List[str]
    actionable_recommendations: List[ActionableRecommendation]
    customer_impact: str

class SummarizationResult(BaseModel):
    tool_name: str
    analysis: Optional[SummaryAnalysis] = None
    summary: Optional[str] = None
    error: Optional[str] = None

# Static functions for tools (not class methods)
@function_tool
def sentiment_analysis(feedback_text: str) -> SentimentAnalysisResult:
    """Perform sentiment analysis on feedback text"""
    try:
        # Using TextBlob for basic sentiment
        blob = TextBlob(feedback_text)
        polarity = blob.sentiment.polarity
        subjectivity = blob.sentiment.subjectivity
        
        # Determine sentiment category
        if polarity > 0.1:
            sentiment = "positive"
        elif polarity < -0.1:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        # Enhanced analysis with OpenAI
        prompt = f"""
        Analyze the sentiment of this customer feedback with detailed reasoning:
        
        Feedback: "{feedback_text}"
        
        Provide analysis in JSON format:
        {{
            "sentiment": "positive/negative/neutral",
            "confidence": 0.9,
            "emotional_indicators": ["list of emotional words/phrases"],
            "sentiment_reasoning": "explanation of why this sentiment was determined"
        }}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        enhanced_data = json.loads(response.choices[0].message.content)
        enhanced_analysis = EnhancedSentimentAnalysis(**enhanced_data)
        
        return SentimentAnalysisResult(
            tool_name="sentiment_analysis",
            basic_sentiment=sentiment,
            polarity_score=polarity,
            subjectivity_score=subjectivity,
            enhanced_analysis=enhanced_analysis
        )
    except Exception as e:
        logger.error(f"Sentiment analysis error: {str(e)}")
        return SentimentAnalysisResult(
            tool_name="sentiment_analysis",
            error=str(e),
            basic_sentiment="neutral",
            polarity_score=0.0,
            subjectivity_score=0.0
        )

@function_tool
def topic_categorization(feedback_text: str) -> TopicCategorizationResult:
    """Categorize feedback into predefined topics"""
    try:
        prompt = f"""
        Categorize this customer feedback into relevant topics from the following list:
        {', '.join(PREDEFINED_TOPICS)}
        
        Feedback: "{feedback_text}"
        
        Provide analysis in JSON format:
        {{
            "primary_topic": "most relevant topic",
            "secondary_topics": ["list of other relevant topics"],
            "topic_scores": {{"Product Quality": 0.8, "Delivery": 0.6}},
            "reasoning": "explanation of categorization"
        }}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        analysis_data = json.loads(response.choices[0].message.content)
        analysis = TopicAnalysis(**analysis_data)
        
        return TopicCategorizationResult(
            tool_name="topic_categorization",
            available_topics=PREDEFINED_TOPICS,
            analysis=analysis
        )
    except Exception as e:
        logger.error(f"Topic categorization error: {str(e)}")
        return TopicCategorizationResult(
            tool_name="topic_categorization",
            available_topics=PREDEFINED_TOPICS,
            error=str(e),
            primary_topic="General"
        )

@function_tool
def keyword_contextualization(feedback_text: str) -> KeywordContextualizationResult:
    """Extract context-aware keywords with relevance scores"""
    try:
        # Basic keyword extraction
        words = re.findall(r'\b\w+\b', feedback_text.lower())
        word_freq = Counter(words)
        
        # Enhanced keyword analysis with OpenAI
        prompt = f"""
        Extract the most important keywords from this customer feedback with context and relevance scores:
        
        Feedback: "{feedback_text}"
        
        Provide analysis in JSON format:
        {{
            "keywords": [
                {{
                    "keyword": "word/phrase",
                    "relevance_score": 0.8,
                    "context": "why this keyword is important",
                    "category": "product/service/experience/issue"
                }}
            ],
            "key_phrases": ["important phrases extracted"],
            "entities": ["people/places/products mentioned"]
        }}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        enhanced_data = json.loads(response.choices[0].message.content)
        enhanced_analysis = EnhancedKeywordAnalysis(**enhanced_data)
        
        return KeywordContextualizationResult(
            tool_name="keyword_contextualization",
            word_frequency=dict(word_freq.most_common(10)),
            enhanced_analysis=enhanced_analysis
        )
    except Exception as e:
        logger.error(f"Keyword extraction error: {str(e)}")
        return KeywordContextualizationResult(
            tool_name="keyword_contextualization",
            word_frequency={},
            error=str(e),
            keywords=[]
        )

@function_tool
def summarization(feedback_text: str, analysis_results: Optional[str] = None) -> SummarizationResult:
    """Generate concise summaries and actionable recommendations"""
    try:
        context = ""
        if analysis_results:
            context = f"""
            Previous analysis context: {analysis_results}
            """
        
        prompt = f"""
        Create a comprehensive summary and actionable recommendations for this customer feedback:
        
        Feedback: "{feedback_text}"
        {context}
        
        Provide analysis in JSON format:
        {{
            "executive_summary": "brief 2-3 sentence summary",
            "key_points": ["list of main points from feedback"],
            "actionable_recommendations": [
                {{
                    "action": "specific action to take",
                    "priority": "high",
                    "department": "which team should handle this",
                    "timeline": "suggested timeframe"
                }}
            ],
            "customer_impact": "assessment of impact on customer experience"
        }}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        analysis_data = json.loads(response.choices[0].message.content)
        analysis = SummaryAnalysis(**analysis_data)
        
        return SummarizationResult(
            tool_name="summarization",
            analysis=analysis
        )
    except Exception as e:
        logger.error(f"Summarization error: {str(e)}")
        return SummarizationResult(
            tool_name="summarization",
            error=str(e),
            summary="Error generating summary"
        )

def get_feedback_agent():
    """Create and return the feedback analysis agent"""
    feedback_analysis_agent = Agent(
        name="Feedback Processing Agent",
        instructions="""
            You are a Feedback Processing Agent. Your role is to determine the appropriate analysis strategy for customer feedback based on provided instructions and the content of the feedback.

            Responsibilities:
            - Interpret the 'instructions' field and feedback text to decide which tools to use.
            - Dynamically determine the execution and optimal sequence of the tools.
            - If no specific instructions are given, apply **all available tools** in a logical order.
            - Always conclude with the `summarization` tool to generate a final structured output.

            Available tools:
            - sentiment_analysis: Analyze the emotional tone and sentiment of the feedback.
            - topic_categorization: Categorize the feedback into relevant business topics.
            - keyword_contextualization: Extract and highlight key phrases and keywords.
            - summarization: Generate a summary and actionable insights using context from previous tools.

            Notes:
            - Always include `summarization` as the final step, using outputs from previous tools.

            Final Output Format:
            The summarization tool must return the final output in the following structured JSON format:
            {
                "executive_summary": "brief 2-3 sentence summary",
                "key_points": ["list of main points from feedback"],
                "actionable_recommendations": [
                    {
                        "action": "specific action to take",
                        "priority": "high/medium/low",
                        "department": "which team should handle this",
                        "timeline": "suggested timeframe"
                    }
                ],
                "customer_impact": "assessment of impact on customer experience"
            }

            Always ensure the final response strictly follows this format.
        """,
        tools=[sentiment_analysis, topic_categorization, keyword_contextualization, summarization],
        output_type=SummaryAnalysis
    )
    return feedback_analysis_agent

def lambda_handler(event, context):
    """Main handler for tool agent"""
    try:
        # Process SQS messages
        for record in event['Records']:
            if isinstance(record['body'], str):
                message_body = json.loads(record['body'])
            else:
                message_body = record['body']
            feedback_data = message_body['feedback_data']
            request_id = message_body['request_id']
            
            logger.info(f"Processing feedback: {feedback_data['feedback_id']}")
            
            # Execute selected tools
            results = {
                "feedback_id": feedback_data['feedback_id'],
                "request_id": request_id,
                "analysis": {},
                "processing_timestamp": datetime.utcnow().isoformat()
            }
            
            agent_input = f"""
                Process this customer feedback:
                
                Feedback: {feedback_data['feedback_text']}
                Instructions: {feedback_data.get('instructions', 'No specific instructions provided')}
            """
            feedback_agent = get_feedback_agent()

            result = Runner.run_sync(
                feedback_agent,
                input=agent_input,
            )
            result = result.final_output
            # print(f"Tool agent result: {result}")
            json_result = json.dumps(result.model_dump(), indent=2)
            print("json_result", json_result)

            # Update state in DynamoDB
            timestamp = int(datetime.fromisoformat(feedback_data['timestamp'].replace('Z', '+00:00')).timestamp())

            results['analysis'] = json_result
            
            state_table.update_item(
                Key={
                    'feedback_id': feedback_data['feedback_id'],
                    'timestamp': timestamp
                },
                UpdateExpression='SET #status = :status, #results = :results, #updated_at = :updated_at',
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#results': 'results',
                    '#updated_at': 'updated_at'
                },
                ExpressionAttributeValues={
                    ':status': 'completed',
                    ':results': results,
                    ':updated_at': datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"Completed processing for feedback: {feedback_data['feedback_id']}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully processed feedback')
        }
        
    except Exception as e:
        logger.error(f"Error in tool agent: {str(e)}")
        raise e