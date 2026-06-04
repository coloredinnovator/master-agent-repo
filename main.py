# Main application file

from agents.task_breakdown_agent.task_breakdown_agent import TaskBreakdownAgent
from agents.research_agent.research_agent import ResearchAgent
from agents.execution_agent.execution_agent import ExecutionAgent

def main():
    # Get high-level goal from user
    high_level_goal = input("Enter your high-level goal: ")

    # Initialize agents
    task_breakdown_agent = TaskBreakdownAgent()
    research_agent = ResearchAgent()
    execution_agent = ExecutionAgent()

    # Break down the high-level goal into sub-tasks
    sub_tasks = task_breakdown_agent.breakdown_task(high_level_goal)

    # Execute each sub-task
    for sub_task in sub_tasks:
        # Research the sub-task
        research_results = research_agent.research(sub_task)

        # Execute the sub-task with the research results
        execution_result = execution_agent.execute(research_results)

        # Print the result of the execution
        print(execution_result)

if __name__ == "__main__":
    main()

