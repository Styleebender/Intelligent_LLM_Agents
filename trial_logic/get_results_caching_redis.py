import json
import os
import boto3
import logging
import time
from typing import Dict, Any, Optional
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
state_table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

# Initialize ElastiCache client (Redis)
try:
    import redis
    redis_client = redis.Redis(
        host=os.environ.get('REDIS_ENDPOINT', 'localhost'),
        port=int(os.environ.get('REDIS_PORT', 6379)),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    REDIS_AVAILABLE = True
except (ImportError, Exception) as e:
    logger.warning(f"Redis not available: {str(e)}. Using in-memory cache.")
    REDIS_AVAILABLE = False
    # In-memory cache as fallback
    in_memory_cache = {}

class CacheManager:
    """Manages caching operations with Redis primary and in-memory fallback"""
    
    def __init__(self):
        self.cache_ttl = int(os.environ.get('CACHE_TTL_SECONDS', 300))  # 5 minutes default
        self.cache_key_prefix = "feedback_results:"
    
    def _get_cache_key(self, feedback_id: str) -> str:
        """Generate cache key for feedback ID"""
        return f"{self.cache_key_prefix}{feedback_id}"
    
    def get(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """Get cached results"""
        cache_key = self._get_cache_key(feedback_id)
        
        try:
            if REDIS_AVAILABLE:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    logger.info(f"Cache HIT for feedback_id: {feedback_id}")
                    return json.loads(cached_data)
            else:
                # In-memory cache with TTL check
                if cache_key in in_memory_cache:
                    cache_entry = in_memory_cache[cache_key]
                    if time.time() < cache_entry['expires_at']:
                        logger.info(f"Memory cache HIT for feedback_id: {feedback_id}")
                        return cache_entry['data']
                    else:
                        # Remove expired entry
                        del in_memory_cache[cache_key]
            
            logger.info(f"Cache MISS for feedback_id: {feedback_id}")
            return None
            
        except Exception as e:
            logger.error(f"Cache retrieval error: {str(e)}")
            return None
    
    def set(self, feedback_id: str, data: Dict[str, Any]) -> bool:
        """Store results in cache"""
        cache_key = self._get_cache_key(feedback_id)
        
        try:
            if REDIS_AVAILABLE:
                redis_client.setex(
                    cache_key, 
                    self.cache_ttl, 
                    json.dumps(data, default=str)
                )
                logger.info(f"Cached results for feedback_id: {feedback_id} (TTL: {self.cache_ttl}s)")
            else:
                # In-memory cache with TTL
                in_memory_cache[cache_key] = {
                    'data': data,
                    'expires_at': time.time() + self.cache_ttl
                }
                logger.info(f"Memory cached results for feedback_id: {feedback_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Cache storage error: {str(e)}")
            return False
    
    def invalidate(self, feedback_id: str) -> bool:
        """Remove specific feedback from cache"""
        cache_key = self._get_cache_key(feedback_id)
        
        try:
            if REDIS_AVAILABLE:
                redis_client.delete(cache_key)
            else:
                in_memory_cache.pop(cache_key, None)
            
            logger.info(f"Cache invalidated for feedback_id: {feedback_id}")
            return True
            
        except Exception as e:
            logger.error(f"Cache invalidation error: {str(e)}")
            return False

class ResultsRetriever:
    """Service to retrieve and format feedback analysis results with caching"""
    
    def __init__(self):
        self.cache_manager = CacheManager()
        self.status_messages = {
            'processing': 'Feedback is still being processed',
            'completed': 'Analysis completed successfully',
            'failed': 'Analysis failed - please try again',
            'not_found': 'Feedback ID not found'
        }
    
    def get_feedback_results(self, feedback_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """Retrieve feedback results with caching support"""
        # Check cache first if enabled
        if use_cache:
            cached_result = self.cache_manager.get(feedback_id)
            if cached_result:
                # Add cache metadata
                cached_result['cache_hit'] = True
                cached_result['retrieved_from'] = 'cache'
                return cached_result
        
        # Cache miss - fetch from DynamoDB
        try:
            response = state_table.query(
                KeyConditionExpression=Key('feedback_id').eq(feedback_id),
                ScanIndexForward=False,  # Get latest record first
                Limit=1
            )
            
            if not response['Items']:
                result = {
                    'status': 'not_found',
                    'message': self.status_messages['not_found'],
                    'feedback_id': feedback_id,
                    'cache_hit': False,
                    'retrieved_from': 'database'
                }
                return result
            
            record = response['Items'][0]
            result = self._format_response(record)
            result['cache_hit'] = False
            result['retrieved_from'] = 'database'
            
            # Cache the result if it's completed (don't cache processing status)
            if use_cache and result.get('status') == 'completed':
                self.cache_manager.set(feedback_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving feedback results: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error retrieving results: {str(e)}',
                'feedback_id': feedback_id,
                'cache_hit': False,
                'retrieved_from': 'error'
            }
    
    def invalidate_cache(self, feedback_id: str) -> bool:
        """Invalidate cache for specific feedback ID"""
        return self.cache_manager.invalidate(feedback_id)
    
    def _format_response(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Format the DynamoDB record into a structured response"""
        status = record.get('status', 'completed')
        
        # Base response structure
        response = {
            'feedback_id': record['feedback_id'],
            'status': status,
            'message': self.status_messages.get(status, 'Analysis results available'),
            'created_at': record.get('created_at'),
            'updated_at': record.get('updated_at'),
            'processing_timestamp': record.get('processing_timestamp'),
            'request_id': record.get('request_id'),
            'original_data': record.get('original_data', {}),
            'cache_metadata': {
                'cacheable': status == 'completed',
                'cache_ttl': int(os.environ.get('CACHE_TTL_SECONDS', 300))
            }
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
            if 'results' in record:
                results = record['results']
                
                if isinstance(results, dict):
                    if 'analysis' in results:
                        analysis_str = results['analysis']
                        if isinstance(analysis_str, str):
                            return json.loads(analysis_str)
                        return analysis_str
                    elif 'executive_summary' in results:
                        return results
                
                elif isinstance(results, str):
                    return json.loads(results)
            
            elif 'analysis' in record:
                analysis_str = record['analysis']
                if isinstance(analysis_str, str):
                    return json.loads(analysis_str)
                return analysis_str
            
            return {}
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error parsing analysis data: {str(e)}")
            return {}
    
    def _structure_analysis_results(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Structure the analysis results in a user-friendly format"""
        if not analysis_data:
            return {
                'summary': 'Analysis results not available',
                'error': 'No analysis data found'
            }
        
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
            
            if priority in formatted['by_priority']:
                formatted['by_priority'][priority].append(rec)
            
            if department not in formatted['by_department']:
                formatted['by_department'][department] = []
            formatted['by_department'][department].append(rec)
            
            if priority == 'high' or rec.get('timeline', '').lower() in ['immediate', 'urgent', '24 hours', 'within the next 2 weeks']:
                formatted['immediate_actions'].append({
                    'action': rec.get('action', ''),
                    'department': department,
                    'timeline': rec.get('timeline', ''),
                    'priority': priority
                })
        
        return formatted

def lambda_handler(event, context):
    """Main handler for results retrieval with caching"""
    try:
        # Extract feedback_id and cache preference
        feedback_id = None
        use_cache = True  # Default to using cache
        force_refresh = False
        
        # API Gateway path parameters
        if event.get('pathParameters') and event['pathParameters']:
            feedback_id = event['pathParameters'].get('feedback_id')
        
        # Query string parameters
        elif event.get('queryStringParameters') and event['queryStringParameters']:
            feedback_id = event['queryStringParameters'].get('feedback_id')
            use_cache = event['queryStringParameters'].get('use_cache', 'true').lower() == 'true'
            force_refresh = event['queryStringParameters'].get('force_refresh', 'false').lower() == 'true'
        
        # Request body
        elif event.get('body'):
            body = event['body']
            if isinstance(body, str):
                body = json.loads(body)
            feedback_id = body.get('feedback_id')
            use_cache = body.get('use_cache', True)
            force_refresh = body.get('force_refresh', False)
        
        # Direct invocation
        else:
            feedback_id = event.get('feedback_id')
            use_cache = event.get('use_cache', True)
            force_refresh = event.get('force_refresh', False)
        
        if not feedback_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing required parameter: feedback_id',
                    'usage': 'Provide feedback_id in path parameters, query parameters, or request body',
                    'cache_options': {
                        'use_cache': 'true/false - Enable/disable cache lookup',
                        'force_refresh': 'true/false - Force refresh from database'
                    }
                })
            }
        
        # Initialize retriever
        retriever = ResultsRetriever()
        
        # Handle force refresh
        if force_refresh:
            retriever.invalidate_cache(feedback_id)
            use_cache = False  # Skip cache lookup after invalidation
        
        # Get results
        results = retriever.get_feedback_results(feedback_id, use_cache=use_cache)
        
        # Determine HTTP status code based on results
        status_code_map = {
            'not_found': 404,
            'error': 500,
            'processing': 202,
            'failed': 422,
            'completed': 200
        }
        status_code = status_code_map.get(results['status'], 200)
        
        # Add performance metadata
        results['performance'] = {
            'cache_enabled': use_cache,
            'cache_hit': results.get('cache_hit', False),
            'retrieved_from': results.get('retrieved_from', 'unknown'),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Retrieved results for feedback_id: {feedback_id}, "
                   f"status: {results['status']}, cache_hit: {results.get('cache_hit', False)}")
        
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'X-Cache-Status': 'HIT' if results.get('cache_hit') else 'MISS'
            },
            'body': json.dumps(results, default=str)
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
                'details': str(e),
                'cache_enabled': False
            })
        }