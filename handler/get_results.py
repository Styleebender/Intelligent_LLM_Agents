import json
import os
import boto3
import logging
from typing import Dict, Any
from boto3.dynamodb.conditions import Key

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
state_table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

class ResultsRetriever:
    """Service to retrieve and format feedback analysis results"""
    
    def __init__(self):
        self.status_messages = {
            'processing': 'Feedback is still being processed',
            'completed': 'Analysis completed successfully',
            'failed': 'Analysis failed - please try again',
            'not_found': 'Feedback ID not found'
        }
    
    def get_feedback_results(self, feedback_id: str) -> Dict[str, Any]:
        """Retrieve feedback results from DynamoDB"""
        try:
            # Query DynamoDB for the feedback record
            response = state_table.query(
                KeyConditionExpression=Key('feedback_id').eq(feedback_id),
                ScanIndexForward=False,  # Get latest record first
                Limit=1
            )
            
            if not response['Items']:
                return {
                    'status': 'not_found',
                    'message': self.status_messages['not_found'],
                    'feedback_id': feedback_id
                }
            
            record = response['Items'][0]
            return self._format_response(record)
            
        except Exception as e:
            logger.error(f"Error retrieving feedback results: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error retrieving results: {str(e)}',
                'feedback_id': feedback_id
            }
    
    def _format_response(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Format the DynamoDB record into a structured response"""
        status = record.get('status', 'completed')  # Default to completed if analysis exists
        
        # Base response structure
        response = {
            'feedback_id': record['feedback_id'],
            'status': status,
            'message': self.status_messages.get(status, 'Analysis results available'),
            'created_at': record.get('created_at'),
            'updated_at': record.get('updated_at'),
            'processing_timestamp': record.get('processing_timestamp'),
            'request_id': record.get('request_id'),
            'original_data': record.get('original_data', {})
        }
        
        # If processing is still ongoing
        if status == 'processing':
            response['estimated_completion'] = 'Within 2-3 minutes'
            return response
        
        # Extract and structure analysis results
        analysis_data = self._extract_analysis_data(record)
        if analysis_data:
            response['results'] = self._structure_analysis_results(analysis_data)
            response['status'] = 'completed'
            response['message'] = self.status_messages['completed']
        else:
            response['status'] = 'failed'
            response['message'] = 'Analysis results not found or corrupted'
            response['results'] = {}
        
        return response
    
    def _extract_analysis_data(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Extract analysis data from the DynamoDB record"""
        try:
            # Check if 'results' field exists first (your actual column name)
            if 'results' in record:
                results = record['results']
                
                # If results is a dict with nested structure
                if isinstance(results, dict):
                    # Check if 'analysis' key exists within results
                    if 'analysis' in results:
                        analysis_str = results['analysis']
                        if isinstance(analysis_str, str):
                            return json.loads(analysis_str)
                        return analysis_str
                    # If results itself contains the analysis data
                    elif 'executive_summary' in results:
                        return results
                
                # If results is a string, try to parse it
                elif isinstance(results, str):
                    return json.loads(results)
            
            # Fallback: check if 'analysis' field exists at root level
            elif 'analysis' in record:
                analysis_str = record['analysis']
                if isinstance(analysis_str, str):
                    return json.loads(analysis_str)
                return analysis_str
            
            return {}
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error parsing analysis data: {str(e)}")
            logger.error(f"Record structure: {json.dumps(record, default=str, indent=2)}")
            return {}
    
    def _structure_analysis_results(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Structure the analysis results in a user-friendly format"""
        if not analysis_data:
            return {
                'summary': 'Analysis results not available',
                'error': 'No analysis data found'
            }
        
        # Extract main components
        structured_results = {
            'executive_summary': analysis_data.get('executive_summary', 'Summary not available'),
            'key_insights': {
                'main_points': analysis_data.get('key_points', []),
                'customer_impact_assessment': analysis_data.get('customer_impact', 'Not assessed')
            },
            'actionable_recommendations': self._format_recommendations(
                analysis_data.get('actionable_recommendations', [])
            ),
            'analysis_confidence': 'High' if analysis_data.get('executive_summary') else 'Low'
        }
        
        return structured_results
    
    def _format_recommendations(self, recommendations: list) -> Dict[str, Any]:
        """Format actionable recommendations by priority and department"""
        if not recommendations:
            return {'message': 'No specific recommendations generated'}
        
        formatted = {
            'total_recommendations': len(recommendations),
            'by_priority': {'high': [], 'medium': [], 'low': []},
            'by_department': {},
            'immediate_actions': [],
            'detailed_recommendations': recommendations
        }
        
        for rec in recommendations:
            priority = rec.get('priority', 'medium').lower()
            department = rec.get('department', 'General')
            
            # Group by priority
            if priority in formatted['by_priority']:
                formatted['by_priority'][priority].append(rec)
            
            # Group by department
            if department not in formatted['by_department']:
                formatted['by_department'][department] = []
            formatted['by_department'][department].append(rec)
            
            # Identify immediate actions
            if priority == 'high' or rec.get('timeline', '').lower() in ['immediate', 'urgent', '24 hours', 'within the next 2 weeks']:
                formatted['immediate_actions'].append({
                    'action': rec.get('action', ''),
                    'department': department,
                    'timeline': rec.get('timeline', ''),
                    'priority': priority
                })
        
        return formatted

def lambda_handler(event, context):
    """Main handler for results retrieval"""
    try:
        # Extract feedback_id from various event sources
        feedback_id = None
        
        # API Gateway path parameters
        if event.get('pathParameters') and event['pathParameters']:
            feedback_id = event['pathParameters'].get('feedback_id')
        
        # Query string parameters
        elif event.get('queryStringParameters') and event['queryStringParameters']:
            feedback_id = event['queryStringParameters'].get('feedback_id')
        
        # Request body (JSON string or dict)
        elif event.get('body'):
            body = event['body']
            if isinstance(body, str):
                body = json.loads(body)
            feedback_id = body.get('feedback_id')
        
        # Direct invocation
        else:
            feedback_id = event.get('feedback_id')
        
        if not feedback_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing required parameter: feedback_id',
                    'usage': 'Provide feedback_id in path parameters, query parameters, or request body'
                })
            }
        
        # Initialize retriever and get results
        retriever = ResultsRetriever()
        results = retriever.get_feedback_results(feedback_id)
        
        # Determine HTTP status code based on results
        status_code_map = {
            'not_found': 404,
            'error': 500,
            'processing': 202,  # Accepted, still processing
            'failed': 422,  # Unprocessable Entity
            'completed': 200
        }
        status_code = status_code_map.get(results['status'], 200)
        
        logger.info(f"Retrieved results for feedback_id: {feedback_id}, status: {results['status']}")
        
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(results, default=str)  # Convert to JSON string with date serialization
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in results retrieval: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred while retrieving results',
                'details': str(e)
            })
        }