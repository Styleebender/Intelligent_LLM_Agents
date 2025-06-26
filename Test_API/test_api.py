"""
API Test Script for Intelligent LLM Agent with Dynamic Tool Selection
Tests the complete multi-agent workflow as per assignment requirements
"""

import requests
import json
import time
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

class LLMAgentTester:
    def __init__(self, base_url: str, get_results_url: str = None):
        """
        Initialize the tester with API endpoints
        
        Args:
            base_url: URL for the User Agent Lambda (API Gateway endpoint)
            get_results_url: URL for the Get Results Lambda (optional, can be same as base_url)
        """
        self.base_url = base_url.rstrip('/')
        self.get_results_url = get_results_url or self.base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def send_feedback(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send feedback to the User Agent"""
        try:
            print(f"🚀 Sending feedback: {feedback_data['feedback_id']}")
            print(f"📝 Instructions: {feedback_data.get('instructions', 'None')}")
            
            response = self.session.post(
                f"{self.base_url}",
                json=feedback_data,
                timeout=30
            )
            
            print(f"📡 Response Status: {response.status_code}")
            
            if response.status_code == 202:
                result = response.json()
                print(f"✅ Feedback accepted: {result}")
                return result
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                return {"error": response.text, "status_code": response.status_code}
                
        except requests.exceptions.RequestException as e:
            print(f"🔥 Request failed: {str(e)}")
            return {"error": str(e)}
    
    def get_results(self, feedback_id: str, max_retries: int = 10, delay: int = 3) -> Dict[str, Any]:
        """Get results from the Get Results Lambda with retry logic"""
        print(f"🔍 Fetching results for feedback_id: {feedback_id}")
        

        for attempt in range(max_retries):
            try:
                request_body = {"feedback_id": feedback_id}

                response = self.session.post(
                    f"{self.get_results_url}",  
                    json=request_body,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Parse the nested JSON in body if needed
                    if isinstance(result.get('body'), str):
                        body_data = json.loads(result['body'])
                        if body_data.get('status') == 'completed':
                            print(f"✅ Results retrieved successfully")
                            return body_data
                        elif body_data.get('status') == 'processing':
                            print(f"⏳ Still processing... (attempt {attempt + 1}/{max_retries})")
                        else:
                            print(f"❓ Unexpected status: {body_data.get('status')}")
                    else:
                        if result.get('status') == 'completed':
                            print(f"✅ Results retrieved successfully")
                            return result
                        elif result.get('status') == 'processing':
                            print(f"⏳ Still processing... (attempt {attempt + 1}/{max_retries})")
                        else:
                            print(f"❓ Unexpected status: {result.get('status')}")
                
                elif response.status_code == 404:
                    print(f"❌ Feedback not found: {feedback_id}")
                    return {"error": "Feedback not found", "status_code": 404}
                else:
                    print(f"❌ Error: {response.status_code} - {response.text}")
                
                if attempt < max_retries - 1:
                    print(f"⏸️  Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                    
            except requests.exceptions.RequestException as e:
                print(f"🔥 Request failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
        
        return {"error": "Max retries exceeded", "status": "timeout"}
    
    def run_test_case(self, test_name: str, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run a complete test case"""
        print(f"\n{'='*60}")
        print(f"🧪 TEST CASE: {test_name}")
        print(f"{'='*60}")
        
        # Step 1: Send feedback
        send_result = self.send_feedback(feedback_data)
        if "error" in send_result:
            return {"test_name": test_name, "status": "failed", "error": send_result["error"]}
        
        # Step 2: Wait and get results
        print(f"\n⏳ Waiting for processing to complete...")
        time.sleep(5)  # Initial wait
        
        results = self.get_results(feedback_data["feedback_id"])
        
        if "error" in results:
            return {
                "test_name": test_name,
                "status": "failed",
                "error": results["error"],
                "send_result": send_result
            }
        
        # Step 3: Analyze results
        return {
            "test_name": test_name,
            "status": "success",
            "send_result": send_result,
            "results": results,
            "analysis_summary": self.analyze_results(results, feedback_data.get("instructions", ""))
        }
    
    def analyze_results(self, results: Dict[str, Any], instructions: str) -> Dict[str, Any]:
        """Analyze the results to check if they match the instructions"""
        analysis = {
            "has_executive_summary": False,
            "has_actionable_recommendations": False,
            "has_key_insights": False,
            "instruction_compliance": "unknown"
        }
        
        # Check if results contain expected components
        if "results" in results and isinstance(results["results"], dict):
            result_data = results["results"]
        elif isinstance(results.get("results"), str):
            try:
                result_data = json.loads(results["results"])
            except:
                result_data = {}
        else:
            result_data = {}
        
        analysis["has_executive_summary"] = "executive_summary" in result_data
        analysis["has_actionable_recommendations"] = "actionable_recommendations" in result_data
        analysis["has_key_insights"] = "key_insights" in result_data
        
        # Check instruction compliance
        if instructions:
            if "sentiment" in instructions.lower():
                analysis["instruction_compliance"] = "partial" if "sentiment" in str(result_data).lower() else "low"
            elif "improvements" in instructions.lower() or "suggest" in instructions.lower():
                analysis["instruction_compliance"] = "high" if "actionable_recommendations" in result_data else "medium"
            else:
                analysis["instruction_compliance"] = "medium"
        else:
            analysis["instruction_compliance"] = "default_execution"
        
        return analysis

def submit_all_test_cases(tester: LLMAgentTester, test_cases: List[Dict]) -> List[Dict]:
    """
    Submit all test cases to the API without waiting for results
    Returns list of submission results with feedback_ids
    """
    print("🚀 Starting batch submission of all test cases...")
    print("=" * 60)
    
    submission_results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📤 Submitting Test Case {i}/{len(test_cases)}: {test_case['name']}")
        print(f"📝 Feedback ID: {test_case['data']['feedback_id']}")
        print(f"📋 Instructions: {test_case['data'].get('instructions', 'None')}")
        
        # Submit the feedback
        submit_result = tester.send_feedback(test_case['data'])
        
        submission_info = {
            "test_name": test_case['name'],
            "feedback_id": test_case['data']['feedback_id'],
            "instructions": test_case['data'].get('instructions', ''),
            "customer_name": test_case['data'].get('customer_name', ''),
            "feedback_text": test_case['data'].get('feedback_text', ''),
            "timestamp": test_case['data'].get('timestamp', ''),
            "submission_result": submit_result,
            "submission_status": "success" if "error" not in submit_result else "failed",
            "submitted_at": datetime.now(timezone.utc).isoformat()
        }
        
        submission_results.append(submission_info)
        
        if "error" in submit_result:
            print(f"❌ Submission failed: {submit_result['error']}")
        else:
            print(f"✅ Submission successful")
        
        # Small delay between submissions to avoid overwhelming the API
        if i < len(test_cases):
            time.sleep(1)
    
    print(f"\n📊 SUBMISSION SUMMARY:")
    successful_submissions = [r for r in submission_results if r["submission_status"] == "success"]
    failed_submissions = [r for r in submission_results if r["submission_status"] == "failed"]
    
    print(f"✅ Successful Submissions: {len(successful_submissions)}/{len(submission_results)}")
    print(f"❌ Failed Submissions: {len(failed_submissions)}/{len(submission_results)}")
    
    if failed_submissions:
        print(f"\n❌ FAILED SUBMISSIONS:")
        for sub in failed_submissions:
            print(f"  - {sub['test_name']}: {sub['submission_result'].get('error', 'Unknown error')}")
    
    return submission_results

def check_all_results(tester: LLMAgentTester, submission_results: List[Dict]) -> List[Dict]:
    """
    Check results for all successfully submitted test cases
    """
    print(f"\n🔍 Checking results for all submitted test cases...")
    print("=" * 60)
    
    final_results = []
    successful_submissions = [r for r in submission_results if r["submission_status"] == "success"]
    
    if not successful_submissions:
        print("❌ No successful submissions to check results for")
        return final_results
    
    for i, submission in enumerate(successful_submissions, 1):
        print(f"\n📋 Checking Results {i}/{len(successful_submissions)}: {submission['test_name']}")
        print(f"🆔 Feedback ID: {submission['feedback_id']}")
        
        # Get results (with reduced retries since we're checking after the wait period)
        results = tester.get_results(submission['feedback_id'], max_retries=3, delay=2)
        
        final_result = {
            "test_name": submission['test_name'],
            "feedback_id": submission['feedback_id'],
            "instructions": submission['instructions'],
            "customer_name": submission['customer_name'],
            "feedback_text": submission['feedback_text'],
            "timestamp": submission['timestamp'],
            "submission_result": submission['submission_result'],
            "submitted_at": submission['submitted_at'],
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "status": "success" if "error" not in results else "failed"
        }
        
        if "error" in results:
            final_result["error"] = results["error"]
            print(f"❌ Failed to get results: {results['error']}")
        else:
            final_result["results"] = results
            final_result["analysis_summary"] = tester.analyze_results(results, submission['instructions'])
            print(f"✅ Results retrieved successfully")
            
            # Show brief analysis
            analysis = final_result["analysis_summary"]
            print(f"   └── Has Executive Summary: {analysis.get('has_executive_summary', False)}")
            print(f"   └── Has Recommendations: {analysis.get('has_actionable_recommendations', False)}")
            print(f"   └── Instruction Compliance: {analysis.get('instruction_compliance', 'N/A')}")
        
        final_results.append(final_result)
    
    return final_results

def display_detailed_results(final_results: List[Dict]):
    """
    Display detailed results for each test case in a formatted way
    """
    print(f"\n{'='*80}")
    print("📋 DETAILED RESULTS FOR ALL TEST CASES")
    print(f"{'='*80}")
    
    successful_tests = [r for r in final_results if r["status"] == "success"]
    failed_tests = [r for r in final_results if r["status"] == "failed"]
    
    # Display successful test results
    if successful_tests:
        print(f"\n✅ SUCCESSFUL TEST CASES ({len(successful_tests)}/{len(final_results)}):")
        print("-" * 80)
        
        for i, test in enumerate(successful_tests, 1):
            print(f"\n🔸 TEST CASE {i}: {test['test_name']}")
            print("─" * 60)
            
            # Input Data Section
            print("📥 INPUT DATA:")
            print(f"   🆔 Feedback ID: {test['feedback_id']}")
            print(f"   👤 Customer Name: {test['customer_name']}")
            print(f"   📝 Instructions: {test['instructions'] or 'None (Default execution)'}")
            print(f"   💬 Feedback Text: \"{test['feedback_text']}\"")
            print(f"   🕒 Timestamp: {test['timestamp']}")
            
            # Results Section
            print("\n📤 ANALYSIS RESULTS:")
            
            try:
                results_data = test.get('results', {})
                
                # Handle different result formats
                analysis_results = None
                if 'results' in results_data:
                    if isinstance(results_data['results'], dict):
                        analysis_results = results_data['results']
                    elif isinstance(results_data['results'], str):
                        try:
                            analysis_results = json.loads(results_data['results'])
                        except json.JSONDecodeError:
                            print(f"   ⚠️  Raw results (JSON parse failed): {results_data['results'][:200]}...")
                    else:
                        print(f"   ⚠️  Unexpected results format: {type(results_data['results'])}")
                
                if analysis_results:
                    # Executive Summary
                    if 'executive_summary' in analysis_results:
                        print(f"   📊 Executive Summary:")
                        print(f"      {analysis_results['executive_summary']}")
                    
                    # Key Insights
                    if 'key_insights' in analysis_results:
                        insights = analysis_results['key_insights']
                        print(f"\n   🔍 Key Insights:")
                        
                        if isinstance(insights, dict):
                            if 'main_points' in insights:
                                print(f"      📌 Main Points:")
                                for point in insights['main_points']:
                                    print(f"         • {point}")
                            
                            if 'customer_impact_assessment' in insights:
                                print(f"      🎯 Customer Impact: {insights['customer_impact_assessment']}")
                        else:
                            print(f"      {insights}")
                    
                    # Actionable Recommendations
                    if 'actionable_recommendations' in analysis_results:
                        recommendations = analysis_results['actionable_recommendations']
                        print(f"\n   🎯 Actionable Recommendations:")
                        
                        if isinstance(recommendations, dict):
                            total_recs = recommendations.get('total_recommendations', 0)
                            print(f"      📈 Total Recommendations: {total_recs}")
                            
                            # Show immediate actions
                            if 'immediate_actions' in recommendations:
                                immediate = recommendations['immediate_actions']
                                if immediate:
                                    print(f"      ⚡ Immediate Actions:")
                                    for action in immediate:
                                        if isinstance(action, dict):
                                            print(f"         • {action.get('action', 'N/A')} "
                                                  f"[{action.get('priority', 'N/A')}] "
                                                  f"({action.get('department', 'N/A')})")
                                        else:
                                            print(f"         • {action}")
                            
                            # Show by priority
                            if 'by_priority' in recommendations:
                                by_priority = recommendations['by_priority']
                                for priority in ['high', 'medium', 'low']:
                                    if priority in by_priority and by_priority[priority]:
                                        print(f"      🔥 {priority.upper()} Priority:")
                                        for rec in by_priority[priority]:
                                            if isinstance(rec, dict):
                                                print(f"         • {rec.get('action', 'N/A')} "
                                                      f"({rec.get('department', 'N/A')})")
                                            else:
                                                print(f"         • {rec}")
                        else:
                            print(f"      {recommendations}")
                    
                    # Analysis Confidence
                    if 'analysis_confidence' in analysis_results:
                        confidence = analysis_results['analysis_confidence']
                        confidence_icon = "🟢" if confidence == "High" else "🟡" if confidence == "Medium" else "🔴"
                        print(f"\n   {confidence_icon} Analysis Confidence: {confidence}")
                
                # Processing Info
                if 'created_at' in results_data and 'updated_at' in results_data:
                    print(f"\n   ⏱️  Processing Info:")
                    print(f"      Created: {results_data['created_at']}")
                    print(f"      Completed: {results_data['updated_at']}")
                
            except Exception as e:
                print(f"   ❌ Error displaying results: {str(e)}")
                print(f"   📋 Raw results data: {str(test.get('results', {}))[:300]}...")
            
            print("\n" + "─" * 60)
    
    # Display failed test cases
    if failed_tests:
        print(f"\n❌ FAILED TEST CASES ({len(failed_tests)}/{len(final_results)}):")
        print("-" * 80)
        
        for i, test in enumerate(failed_tests, 1):
            print(f"\n🔸 FAILED TEST {i}: {test['test_name']}")
            print("─" * 60)
            
            # Input Data Section
            print("📥 INPUT DATA:")
            print(f"   🆔 Feedback ID: {test['feedback_id']}")
            print(f"   👤 Customer Name: {test['customer_name']}")
            print(f"   📝 Instructions: {test['instructions'] or 'None (Default execution)'}")
            print(f"   💬 Feedback Text: \"{test['feedback_text']}\"")
            
            # Error Information
            print("\n❌ ERROR DETAILS:")
            error_msg = test.get('error', 'Unknown error')
            print(f"   📋 Error: {error_msg}")
            
            if 'submission_result' in test:
                print(f"   📡 Submission Status: {test.get('submission_result', {})}")
            
            print("\n" + "─" * 60)
    
    print(f"\n{'='*80}")

def generate_comprehensive_report(final_results: List[Dict]):
    """Generate a comprehensive test report"""
    print(f"\n{'='*80}")
    print("📊 TEST REPORT")
    print(f"{'='*80}")
    
    successful_tests = [r for r in final_results if r["status"] == "success"]
    failed_tests = [r for r in final_results if r["status"] == "failed"]
    
    print(f"📈 OVERALL STATISTICS:")
    print(f"   Total Tests: {len(final_results)}")
    print(f"   ✅ Successful: {len(successful_tests)}")
    print(f"   ❌ Failed: {len(failed_tests)}")
    print(f"   📊 Success Rate: {(len(successful_tests)/len(final_results)*100):.1f}%" if final_results else "0%")
    
    if failed_tests:
        print(f"\n❌ FAILED TESTS SUMMARY:")
        for test in failed_tests:
            print(f"   - {test['test_name']}")
            print(f"     └── Error: {test.get('error', 'Unknown error')}")
            print(f"     └── Feedback ID: {test['feedback_id']}")
    
    if successful_tests:
        print(f"\n✅ SUCCESSFUL TESTS SUMMARY:")
        for test in successful_tests:
            analysis = test.get('analysis_summary', {})
            print(f"   - {test['test_name']}")
            print(f"     └── Feedback ID: {test['feedback_id']}")
            print(f"     └── Instructions: {test['instructions'] or 'Default execution'}")
            print(f"     └── Compliance: {analysis.get('instruction_compliance', 'N/A')}")
            print(f"     └── Components: Summary={analysis.get('has_executive_summary', False)}, "
                  f"Recommendations={analysis.get('has_actionable_recommendations', False)}, "
                  f"Insights={analysis.get('has_key_insights', False)}")
    
    print(f"\n🎯 Test execution and analysis completed!")

def main():
    """Main test execution with batch approach"""

    print("🧪 Starting API Tests for Intelligent LLM Agent")
    print("=" * 60)
    
    # Configuration - UPDATE THESE URLs WITH YOUR ACTUAL LAMBDA ENDPOINTS
    USER_AGENT_URL = "https://ez4ua5mk22wjjl4ggav2jfg2yi0lckxf.lambda-url.eu-north-1.on.aws/"
    GET_RESULTS_URL = "https://y5pfqxgb3agtqinb2qy2wzyqm40rrrzp.lambda-url.eu-north-1.on.aws/"
    
    # Initialize tester
    tester = LLMAgentTester(USER_AGENT_URL, GET_RESULTS_URL)
    
    # Test Cases as per Assignment Requirements
    test_cases = [
        {
            "name": "Default Execution - No Instructions",
            "data": {
                "feedback_id": "12345",
                "customer_name": "John Doe",
                "feedback_text": "The product is great, but the delivery was delayed.",
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
        },
        {
            "name": "Focused Execution - Sentiment Analysis",
            "data": {
                "feedback_id": "67890",
                "customer_name": "Jane Smith",
                "feedback_text": "The customer service was very helpful, but the website checkout process was confusing.",
                "timestamp": "2025-02-15T14:45:00Z",
                "instructions": "Analyze sentiment and suggest improvements for the checkout process."
            }
        },
        {
            "name": "Complex Instructions - Multiple Tasks",
            "data": {
                "feedback_id": "11111",
                "customer_name": "Mike Johnson",
                "feedback_text": "Love the new features but the app crashes frequently. Support team is responsive though.",
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "instructions": "Identify the key topics and summarize actionable points."
            }
        },
        {
            "name": "Specific Tool Focus - Keywords Only",
            "data": {
                "feedback_id": "22222",
                "customer_name": "Sarah Wilson",
                "feedback_text": "The mobile app interface is outdated and not user-friendly. However, the content is valuable.",
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "instructions": "Focus only on sentiment analysis and keyword extraction."
            }
        },
        {
            "name": "Edge Case - Very Short Feedback",
            "data": {
                "feedback_id": "33333",
                "customer_name": "Tom Brown",
                "feedback_text": "Good product.",
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "instructions": "Provide detailed analysis despite short feedback."
            }
        }
    ]
    
    # PHASE 1: Submit All Test Cases
    print("🔄 PHASE 1: Submitting all test cases...")
    submission_results = submit_all_test_cases(tester, test_cases)
    
    # PHASE 2: Wait for Processing
    wait_time = 45
    print(f"\n⏰ PHASE 2: Waiting {wait_time} seconds for all test cases to process...")
    print("☕ Grab some coffee while the agents work their magic...")
    
    # Show countdown
    for remaining in range(wait_time, 0, -5):
        print(f"⏳ {remaining} seconds remaining...")
        time.sleep(5)
    
    print("✅ Wait period completed! Starting results collection...")
    
    # PHASE 3: Check All Results
    print(f"\n🔍 PHASE 3: Checking results for all test cases...")
    final_results = check_all_results(tester, submission_results)
    
    # NEW PHASE 3.5: Display Detailed Results
    print(f"\n📋 PHASE 3.5: Displaying detailed results for all test cases...")
    display_detailed_results(final_results)
    
    # PHASE 4: Generate Comprehensive Report
    print(f"\n📋 PHASE 4: Generating comprehensive report...")
    generate_comprehensive_report(final_results)
    
    return final_results

if __name__ == "__main__":
    main()