# Memory Collection Flow Diagram

## Quick Conversational Flow (New)

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant Collector as Memory Collector
    participant State as Session State
    participant Pipeline as Pipeline Orchestrator

    User->>Frontend: "My wedding with Alex in 2020"
    Frontend->>API: POST /api/chat/message
    API->>State: Get/Create session state
    State->>Collector: Run with conversation context
    Collector->>Collector: Parse: has What + When + Who?
    
    alt Missing critical info
        Collector->>API: {status: "needs_info", message: "What moment?"}
        API->>Frontend: Return conversational response
        Frontend->>User: Display: "What moment to capture?"
        User->>Frontend: "The ceremony at sunset"
        Frontend->>API: POST /api/chat/message
        API->>State: Add to conversation
        State->>Collector: Run with updated context
    end
    
    Collector->>Collector: Extract structured data
    Collector->>API: {status: "ready", extraction: {...}}
    API->>Pipeline: Trigger automatic progression
    
    Pipeline->>Pipeline: Content Screening
    Pipeline->>Pipeline: Image Generation
    Pipeline->>Pipeline: Photo Upload
    
    Pipeline->>API: {status: "completed", image_url: "..."}
    API->>Frontend: Return with image
    Frontend->>User: Display image + "Memory created!"
```

## State Management

```mermaid
stateDiagram-v2
    [*] --> Collecting
    
    Collecting --> Collecting: Need more info
    Collecting --> Screening: Extraction complete
    
    Screening --> Screening: Validation in progress
    Screening --> PolicyViolation: Content violation
    Screening --> Generating: Content approved
    
    Generating --> Generating: Image creation
    Generating --> Failed: Generation error
    Generating --> Uploading: Image ready
    
    Uploading --> Failed: Upload error
    Uploading --> Completed: Success
    
    PolicyViolation --> [*]
    Failed --> [*]
    Completed --> [*]
```

## Conversation State

```mermaid
classDiagram
    class ConversationState {
        +List~Dict~ messages
        +MemoryExtraction extraction
        +String stage
        +add_message(role, content)
        +get_conversation_context()
    }
    
    class MemoryExtraction {
        +String what_happened
        +DateTime when
        +String when_description
        +List~String~ who_people
        +List~String~ who_pets
        +String where
        +String emotions_mood
        +Bool is_complete
        +List~String~ missing_fields
    }
    
    class MemoryTeam {
        +Dict~String,ConversationState~ sessions
        +TokenTracker token_tracker
        +process_memory()
        +get_session_state()
        -_process_screening()
        -_process_generation()
    }
    
    MemoryTeam --> ConversationState: manages
    ConversationState --> MemoryExtraction: contains
```

## Date Calculation Examples

```mermaid
graph TD
    A[User Input] --> B{Parse Expression}
    
    B -->|"last summer"| C[Calculate: Previous Jun-Aug]
    B -->|"2 years ago"| D[Calculate: Today - 2 years]
    B -->|"Christmas 2020"| E[Use: Dec 25, 2020]
    B -->|"my birthday"| F[Ask: Need birth month]
    
    C --> G[Return DateTime + Explanation]
    D --> G
    E --> G
    F --> H[Request Clarification]
    
    G --> I[Store in MemoryExtraction]
    H --> A
```

## Token Flow

```mermaid
flowchart LR
    A[User Message] -->|1000 tokens| B[Memory Collector]
    B -->|Extraction Complete| C[Content Screener]
    C -->|300 tokens| D[Image Generator]
    D -->|2000 tokens<br/>includes generation| E[Photo Manager]
    E -->|500 tokens| F[Complete]
    
    B -.->|Needs more info<br/>800 tokens| A
    
    style A fill:#e1f5ff
    style F fill:#d4edda
    style B fill:#fff3cd
    style C fill:#fff3cd
    style D fill:#fff3cd
    style E fill:#fff3cd
```

## Comparison: Old vs New

### Old Flow (4-6 exchanges)
```
User: "My wedding"
→ Agent: "When? Where? Who? Describe?"
User: "June 2020 in Napa with Alex"
→ Agent: "What moment?"
User: "The ceremony"
→ Agent: "What time of day?"
User: "Sunset"
→ Agent: "Any other details?"
User: "No"
→ Generate image

Total: 6 exchanges, ~8,000 tokens
```

### New Flow (2-3 exchanges)
```
User: "My wedding with Alex in June 2020"
→ Agent: "What moment would you like to capture?"
User: "The ceremony at sunset"
→ Auto-generate image

Total: 2 exchanges, ~3,500 tokens
```

**Improvement**: 
- 67% fewer exchanges
- 56% fewer tokens
- 50% faster completion
