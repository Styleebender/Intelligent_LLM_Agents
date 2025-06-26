# Intelligent LLM Agent with Dynamic Tool Selection

## Quick Test Agent: ([Google Colab:](https://colab.research.google.com/drive/17b2YtpsqK6w_3saZWxcBJNRWFrqSXyPZ?usp=sharing))

## Project Overview

This project implements a smart, multi-agent LLM-driven solution capable of dynamically deciding which tools to execute based on specific instructions for customer feedback analysis. The system uses AWS services for scalability and real-time processing with asynchronous communication between agents.

## Architecture Overview

### System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │───▶│   User Agent    │───▶│   SQS Queue    │
│                 │    │   (Lambda 1)    │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                      │
                                ▼                      ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   DynamoDB      │◄───│  Tool Agent     │
                       │   State Store   │    │   (Lambda 2)    │
                       └─────────────────┘    └─────────────────┘
                                │                      │
                                ▼                      │
                       ┌─────────────────┐             │
                       │  Get Results    │◄────────────┘
                       │   (Lambda 3)    │
                       └─────────────────┘
```

### Multi-Agent Design

The system consists of three main components:

1. **User Agent (Guardrail Agent)** - Handles user interaction and applies content guardrails
2. **Tool Agent (Feedback Analysis Agent)** - Performs dynamic tool selection and execution
3. **Results Agent** - Retrieves and formats analysis results

## Core Components

### 1. User Agent (Lambda 1)
- **Purpose**: User interaction handler with content guardrails
- **Responsibilities**:
  - Validate incoming requests
  - Apply content filtering guardrails
  - Validate user instructions
  - Store initial state in DynamoDB
  - Queue messages for processing in SQS

### 2. Tool Agent (Lambda 2)
- **Purpose**: Dynamic tool execution based on instructions
- **Responsibilities**:
  - Process SQS messages asynchronously
  - Interpret instructions using LLM
  - Dynamically select and execute tools
  - Update processing state in DynamoDB

### 3. Results Agent (Lambda 3)
- **Purpose**: Results retrieval and formatting
- **Responsibilities**:
  - Query DynamoDB for feedback results
  - Format analysis results for user consumption
  - Handle different processing states

## Available Analysis Tools

### 1. Sentiment Analysis Tool
- **Function**: Analyze emotional tone and sentiment
- **Output**: 
  - Basic sentiment (positive/negative/neutral)
  - Polarity and subjectivity scores
  - Enhanced analysis with emotional indicators
  - Sentiment reasoning

### 2. Topic Categorization Tool
- **Function**: Categorize feedback into predefined business topics
- **Categories**: Product Quality, Delivery, Customer Support, Pricing, Website/App, Billing, Returns, Shipping, User Experience
- **Output**:
  - Primary topic identification
  - Secondary relevant topics
  - Topic confidence scores
  - Categorization reasoning

### 3. Keyword Contextualization Tool
- **Function**: Extract context-aware keywords with relevance scores
- **Output**:
  - Word frequency analysis
  - Keywords with relevance scores and context
  - Key phrases extraction
  - Named entity recognition

### 4. Summarization Tool
- **Function**: Generate concise summaries and actionable recommendations
- **Output**:
  - Executive summary
  - Key points extraction
  - Actionable recommendations with priority and department assignment
  - Customer impact assessment

## Dynamic Tool Selection Logic

The system uses an intelligent agent powered by OpenAI's agents framework to:

1. **Parse Instructions**: Analyze the `instructions` field to understand user requirements
2. **Context Analysis**: Evaluate feedback content to determine relevant tools
3. **Dynamic Execution**: Select appropriate tools based on instructions and content
4. **Default Behavior**: Execute all tools when no specific instructions are provided
5. **Sequential Processing**: Ensure logical tool execution order
6. **Final Summarization**: Always conclude with summarization tool for structured output

### Example Instruction Interpretations:
- `"Focus on sentiment analysis only"` → Execute only sentiment_analysis tool
- `"Analyze sentiment and suggest improvements"` → Execute sentiment_analysis + summarization
- `"Identify key topics and summarize actionable points"` → Execute topic_categorization + summarization
- No instructions → Execute all tools in logical sequence

## Quick Test Agent:
([Google Colab:](https://colab.research.google.com/drive/17b2YtpsqK6w_3saZWxcBJNRWFrqSXyPZ?usp=sharing))

## AWS Services Integration

### AWS Lambda
- **User Agent**: Handles API requests and guardrails
- **Tool Agent**: Processes feedback with dynamic tool selection
- **Results Agent**: Retrieves and formats results

### Amazon SQS
- **Purpose**: Asynchronous communication between agents
- **Queue**: `feedback-processing-queue`
- **Benefits**: Decoupling, reliability, scalability

### Amazon DynamoDB
- **Purpose**: State management and results storage
- **Table Structure**:
  - Primary Key: `feedback_id` (String)
  - Sort Key: `timestamp` (Number)
  - Attributes: `status`, `original_data`, `results`, `created_at`, `updated_at`

### API Gateway
- **Purpose**: REST API endpoints
- **Endpoints**:
  - `POST /feedback` - Submit feedback for analysis
  - `GET /results/{feedback_id}` - Retrieve analysis results

## API Usage Examples

### Submit Feedback for Analysis

```bash
POST /feedback
Content-Type: application/json

{
  "feedback_id": "12345",
  "customer_name": "John Doe",
  "feedback_text": "The product is great, but the delivery was delayed.",
  "timestamp": "2025-01-10T10:30:00Z",
  "instructions": "Focus on identifying the sentiment and summarizing actionable insights."
}
```

**Response:**
```json
{
  "message": "Feedback received and queued for processing",
  "feedback_id": "12345",
  "status": "processing"
}
```

### Retrieve Analysis Results

```bash
GET /results/12345
```

**Response:**
```json
{
  "feedback_id": "12345",
  "status": "completed",
  "message": "Analysis completed successfully",
  "results": {
    "executive_summary": "Customer expresses satisfaction with product quality but frustration with delivery delays.",
    "key_insights": {
      "main_points": [
        "Positive product feedback",
        "Delivery service issues",
        "Overall mixed sentiment"
      ],
      "customer_impact_assessment": "Moderate impact - satisfied with product but delivery issues may affect future purchases"
    },
    "actionable_recommendations": {
      "total_recommendations": 2,
      "immediate_actions": [
        {
          "action": "Review delivery logistics and identify bottlenecks",
          "department": "Operations",
          "timeline": "Within 1 week",
          "priority": "high"
        }
      ]
    }
  }
}
```

## Error Handling

The system implements comprehensive error handling:

1. **Input Validation**: Validates required fields and data types
2. **Content Guardrails**: Filters inappropriate content
3. **Instruction Validation**: Ensures instructions are within scope
4. **Tool Execution**: Handles tool failures gracefully
5. **State Management**: Tracks processing status and errors
6. **Fallback Mechanisms**: Default behaviors when specific tools fail

## Security Features

### Content Guardrails
- **Hate Speech Detection**: Filters harmful content
- **Spam Detection**: Identifies irrelevant content
- **PII Redaction**: Removes personal information
- **Instruction Validation**: Prevents malicious instructions

### Current Limitations
1. **Caching**: Redis caching not implemented (planned enhancement)
2. **Infrastructure as Code**: Manual deployment (Terraform planned)

### Future Enhancements
1. **Redis Caching**: Implement result caching for improved performance
2. **Terraform Deployment**: Complete IaC implementation


---

## Quick Start Guide
## Follow Architecture and Design Decisions & Setup Instructions Documentation
