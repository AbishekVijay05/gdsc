  
**Team Name :** Coders UN Problem Statement : The Autonomous Research Orchestrator: Intelligent Drug Repurposing Platform  
**Contrast Problem Statement :** Extend the system from "Static Report Generation' to "Conversational Orchestration & Stateful Steering." Instead of only executing a one-shot retrieval and synthesis, the system must now act as an interactive research partner, analyzing natural language feedback to dynamically re-route the multi-agent workflow in real-time. The system shifts from passive execution to active, statefiul collaboration.

**Key Challenges:**  
• Intent-to-Constraint Translation: Converting conversational, non-technical feedback (e.g., "gentler on the heart") into precise search parameters for the sub-agents. ○ Conversational State Management: Maintaining a persistent memory of the chat history, rejected candidates, and context across multiple iterations ○ Asynchronous Coordination: Keeping the chat UI fluid and responsive while complex multi-domain data retrieval occurs in the background. • Proactive Clarification: Identifying ambiguous user feedback and autonomously asking clarifying questions before re-tasking agents.  
**Contrast Requirements:**  
**1\. The Translator Orchestrator**  
• Accepts the initial clinical unmet need in natural language.  
• Translates casual feedback into hard agent constraints (e.g., "exclude cardiovascular toxicity")  
• Coordinates the Clinical, Patent, and Market agents to fetch new data based on updated conversational parameters.  
**2, Persistent Chat Interface**  
**Display:**  
• A continuous natural language dialogue window.  
• Live background agent activity feeds (e.g.., "Patent Agent checking IP..").  
• Inline result cards presenting the proposed drug candidates directly within the chat flow  
**3\. Simulation / Interaction Mode**  
Allow simulated conversational pivots such as:  
• Adding a new biological constraint mid-search (e.g., "Must cross the blood-brain barrier") • Rejecting a candidate due to non-technical reasons (e.g., "Too expensive to manufacture")  
• Providing vague feedback to trigger a clarification question from the AI.  
The system must automatically update its search parameters according to the conversation, discard rejected candidates, and generate a newly tailored recommendation without losing context.  
**Expected Outcome:**  
A refined Conversational Orchestration System that:  
• Translates casual chat into strict search constraints  
• Retains stateful context across multiple chat turns  
• Provides UI transparency for background agent tasks  
• Successfully pivots drug candidates based on conversational steering