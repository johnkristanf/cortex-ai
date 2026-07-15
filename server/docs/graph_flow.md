# Agent Graph Flow Documentation

This document describes the state graph flow for the Cortex AI agent, specifically outlining the core agent interactions and the specialized job application workflow.

## Overview

The agent is built using LangGraph (`StateGraph`) with a state managed by `AgentState`. Memory persistence is handled via `MemorySaver`. The graph manages both general conversation and tool execution, as well as a specific state machine for job applications.

## Graph Visualization

```text
================================================================================
                            STATE GRAPH FLOWCHART
================================================================================

Legend:
  ( State )      : Start/End States
  - - - - -      : Graph Nodes (Dashed Boxes)
 /         \     : Routers / Conditional Edges (Diamonds/Triangles)
 \         /
================================================================================

                               ( START )
                                   |
                                   v
                           /---------------\
                          /   entry_point   \
                          \                 /
                           \---------------/
                             |     |     |
            .----------------'     |     '----------------.
            | (Default)            |                      |
            v                      | (Wait for prefs)     | (Wait for resume)
       - - - - - -                 |                      v
 .--->|   agent   |<--.            |               - - - - - - - - -
 |     - - - - - -    |            |              |  resume_upload  |<----.
 |          |         |            |               - - - - - - - - -      |
 |          v         |            |                      |               |
 | /----------------\ |            |                      v               |
 |/   route_model_   \|            |            /-------------------\     |
 |\      output      /|            |           / route_resume_upload \    |
 | \----------------/ |            |           \                     /    |
 |   |      |      |  |            |            \-------------------/     |
 |   |      |      |  |            |              |               |       |
 |   |      |      '--|------------'              |               |       |
 |   |      |   (Tool)|                           |               |       |
 |   |      |         |                           |               v       |
 |   |   - - - - - -  |                           |             ( END )   |
 '---|--|   tools   | |                           |                       |
     |   - - - - - -  |                           | (Profile ready)       |
     |                |                           |                       |
     v                |                           v                       |
   (END)              |                - - - - - - - - - - - - -          |
                      |               | collect_job_preferences |<--------'
  (start_job_app)     |                - - - - - - - - - - - - -          
                      |                           |                       
     .----------------'                           v                       
     v                                   /-----------------\              
 - - - - - - - -                        / route_job_prefs   \             
| resume_check  |                       \                   /             
 - - - - - - - -                         \-----------------/              
       |                                   |             |                
       v                                   |             v                
 /------------\                            |           (END)              
/ route_resume \                           |                              
\              /                           | (Prefs collected)            
 \------------/                            |                              
   |        |                              |                              
   |        '------------------------------|------------------------------'
   |  (Not found)                          |
   |                                       v
   | (Found)                          - - - - - -
   '-------------------------------->| find_jobs |
                                      - - - - - -
                                           |
                                           v
                              [ Loops back to agent ]
```

## Node Descriptions

### Core Nodes
- **`agent` (`agent_node`)**: The primary LLM interaction node. Generates natural language responses, invokes tools, or triggers specific workflows.
- **`tools` (`execute_tools`)**: Executes tool calls requested by the agent and returns the results.

### Job Application Subgraph
- **`resume_check` (`resume_check_node`)**: Checks if a parsed resume profile exists in the user's storage/state.
- **`resume_upload` (`resume_upload_node`)**: Handles the state when waiting for and processing a user's resume upload.
- **`collect_job_preferences` (`collect_job_preferences_node`)**: Prompts the user to collect mandatory job search preferences (e.g., target roles, location, remote work preferences, salary).
- **`find_jobs` (`find_jobs_node`)**: Executes the job search using the gathered preferences and resume profile.

## Routing Logic

### 1. Entry Point (`entry_point`)
Determines the initial node when the graph is invoked, allowing bypass of the main agent if the system is waiting for specific user input.
- **`agent`**: Normal conversational flow.
- **`resume_upload`**: The system previously asked for a resume and is awaiting the upload.
- **`collect_job_preferences`**: The system is in the middle of gathering job preferences.

### 2. Agent Output Routing (`route_model_output`)
After the agent generates a response, this router decides the next step.
- **`tools`**: If the agent produced tool calls.
- **`resume_check`**: If the intent to start a job application was detected.
- **`END`**: If a final response to the user is ready.

### 3. Resume Check Routing (`route_resume`)
Determines next steps after checking for an existing resume.
- **`collect_job_preferences`**: A valid resume profile exists in storage.
- **`resume_upload`**: No resume is found; prompt the user to upload.

### 4. Resume Upload Routing (`route_resume_upload`)
Handles the outcome of the upload phase.
- **`collect_job_preferences`**: The user uploaded a resume and the profile was successfully extracted.
- **`END`**: The system has prompted the user to upload and is waiting for their action.

### 5. Job Preferences Routing (`route_job_preferences`)
Evaluates if all necessary preferences are collected.
- **`find_jobs`**: All required preferences are present.
- **`END`**: Missing preferences; the agent has prompted the user and is waiting for a reply.

### 6. Job Search Completion
- After `find_jobs` executes, the flow unconditionally returns to the **`agent`** node so the LLM can format the job results into a natural-language response for the user.
