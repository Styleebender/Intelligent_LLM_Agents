import json
import os
import boto3
import logging
from datetime import datetime
from typing import Dict, List, Any
from openai import OpenAI
from textblob import TextBlob
import re
from collections import Counter

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb', region_name=os.environ['REGION'])
state_table = dynamodb.Table(os.environ['STATE_TABLE'])

# OpenAI client
openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

class FeedbackAnalysisTools:
    """Collection of analysis tools for customer feedback"""
    
    def __init__(self):
        self.predefined_topics = [
            "Product Quality", "Delivery", "Customer Support", "Pricing", 
            "Website/App", "Billing", "Returns", "Shipping", "User Experience"
        ]
    
    def sentiment_analysis(self, feedback_text: str) -> Dict[str, Any]:
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
                "confidence": 0.0-1.0,
                "emotional_indicators": ["list of emotional words/phrases"],
                "sentiment_reasoning": "explanation of why this sentiment was determined"
            }}
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            enhanced_analysis = json.loads(response.choices[0].message.content)
            
            return {
                "tool_name": "sentiment_analysis",
                "basic_sentiment": sentiment,
                "polarity_score": polarity,
                "subjectivity_score": subjectivity,
                "enhanced_analysis": enhanced_analysis
            }
        except Exception as e:
            logger.error(f"Sentiment analysis error: {str(e)}")
            return {
                "tool_name": "sentiment_analysis",
                "error": str(e),
                "basic_sentiment": "neutral",
                "polarity_score": 0.0
            }
    
    def topic_categorization(self, feedback_text: str) -> Dict[str, Any]:
        """Categorize feedback into predefined topics"""
        try:
            prompt = f"""
            Categorize this customer feedback into relevant topics from the following list:
            {', '.join(self.predefined_topics)}
            
            Feedback: "{feedback_text}"
            
            Provide analysis in JSON format:
            {{
                "primary_topic": "most relevant topic",
                "secondary_topics": ["list of other relevant topics"],
                "topic_scores": {{"topic": confidence_score}},
                "reasoning": "explanation of categorization"
            }}
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            return {
                "tool_name": "topic_categorization",
                "available_topics": self.predefined_topics,
                "analysis": analysis
            }
        except Exception as e:
            logger.error(f"Topic categorization error: {str(e)}")
            return {
                "tool_name": "topic_categorization",
                "error": str(e),
                "primary_topic": "General"
            }
    
    def keyword_contextualization(self, feedback_text: str) -> Dict[str, Any]:
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
                        "relevance_score": 0.0-1.0,
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
            
            enhanced_analysis = json.loads(response.choices[0].message.content)
            
            return {
                "tool_name": "keyword_contextualization",
                "word_frequency": dict(word_freq.most_common(10)),
                "enhanced_analysis": enhanced_analysis
            }
        except Exception as e:
            logger.error(f"Keyword extraction error: {str(e)}")
            return {
                "tool_name": "keyword_contextualization",
                "error": str(e),
                "keywords": []
            }
    
    def summarization(self, feedback_text: str, analysis_results: Dict = None) -> Dict[str, Any]:
        """Generate concise summaries and actionable recommendations"""
        try:
            context = ""
            if analysis_results:
                context = f"""
                Previous analysis context:
                - Sentiment: {analysis_results.get('sentiment_analysis', {}).get('basic_sentiment', 'unknown')}
                - Primary Topic: {analysis_results.get('topic_categorization', {}).get('analysis', {}).get('primary_topic', 'unknown')}
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
                        "priority": "high/medium/low",
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
            
            analysis = json.loads(response.choices[0].message.content)
            
            return {
                "tool_name": "summarization",
                "analysis": analysis
            }
        except Exception as e:
            logger.error(f"Summarization error: {str(e)}")
            return {
                "tool_name": "summarization",
                "error": str(e),
                "summary": "Error generating summary"
            }

class InstructionInterpreter:
    """Interprets user instructions to determine which tools to execute"""
    
    def __init__(self):
        self.available_tools = [
            "sentiment_analysis",
            "topic_categorization", 
            "keyword_contextualization",
            "summarization"
        ]
    
    def interpret_instructions(self, instructions: str) -> Dict[str, Any]:
        """Determine which tools to execute based on instructions"""
        try:
            if not instructions:
                return {
                    "tools_to_execute": self.available_tools,
                    "execution_order": self.available_tools,
                    "reasoning": "No specific instructions provided, executing all tools"
                }
            
            prompt = f"""
            Based on these instructions for customer feedback analysis, determine which tools should be executed:
            
            Instructions: "{instructions}"
            
            Available tools:
            - sentiment_analysis: Analyzes emotional tone and sentiment
            - topic_categorization: Categorizes feedback into business topics
            - keyword_contextualization: Extracts important keywords and phrases
            - summarization: Creates summaries and actionable recommendations
            
            Respond with JSON:
            {{
                "tools_to_execute": ["list of tool names to run"],
                "execution_order": ["preferred order of execution"],
                "tool_specific_params": {{
                    "tool_name": {{"param": "value"}}
                }},
                "reasoning": "explanation of tool selection"
            }}
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            interpretation = json.loads(response.choices[0].message.content)
            
            # Validate tools exist
            valid_tools = [tool for tool in interpretation["tools_to_execute"] 
                          if tool in self.available_tools]
            
            if not valid_tools:
                valid_tools = self.available_tools
            
            interpretation["tools_to_execute"] = valid_tools
            interpretation["execution_order"] = valid_tools
            
            return interpretation
            
        except Exception as e:
            logger.error(f"Instruction interpretation error: {str(e)}")
            return {
                "tools_to_execute": self.available_tools,
                "execution_order": self.available_tools,
                "reasoning": f"Error interpreting instructions: {str(e)}, defaulting to all tools"
            }

def handler(event, context):
    """Main handler for tool agent"""
    try:
        # Process SQS messages
        for record in event['Records']:
            message_body = json.loads(record['body'])
            feedback_data = message_body['feedback_data']
            request_id = message_body['request_id']
            
            logger.info(f"Processing feedback: {feedback_data['feedback_id']}")
            
            # Initialize components
            tools = FeedbackAnalysisTools()
            interpreter = InstructionInterpreter()
            
            # Interpret instructions to determine tool execution
            instruction_analysis = interpreter.interpret_instructions(
                feedback_data.get('instructions', '')
            )
            
            # Execute selected tools
            results = {
                "feedback_id": feedback_data['feedback_id'],
                "request_id": request_id,
                "instruction_analysis": instruction_analysis,
                "tool_results": {},
                "processing_timestamp": datetime.utcnow().isoformat()
            }
            
            # Execute tools in specified order
            for tool_name in instruction_analysis['execution_order']:
                logger.info(f"Executing tool: {tool_name}")
                
                if tool_name == "sentiment_analysis":
                    result = tools.sentiment_analysis(feedback_data['feedback_text'])
                elif tool_name == "topic_categorization":
                    result = tools.topic_categorization(feedback_data['feedback_text'])
                elif tool_name == "keyword_contextualization":
                    result = tools.keyword_contextualization(feedback_data['feedback_text'])
                elif tool_name == "summarization":
                    result = tools.summarization(feedback_data['feedback_text'], results['tool_results'])
                else:
                    continue
                
                results['tool_results'][tool_name] = result
            
            # Update state in DynamoDB
            timestamp = int(datetime.fromisoformat(feedback_data['timestamp'].replace('Z', '+00:00')).timestamp())
            
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
            
            # Send results to results queue
            sqs.send_message(
                QueueUrl=os.environ['RESULTS_QUEUE_URL'],
                MessageBody=json.dumps(results)
            )
            
            logger.info(f"Completed processing for feedback: {feedback_data['feedback_id']}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully processed feedback')
        }
        
    except Exception as e:
        logger.error(f"Error in tool agent: {str(e)}")
        raise e