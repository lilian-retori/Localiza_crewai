from crewai import Agent, Task, Crew
from app.prompts import TASK_DESCRIPTION
from app.tools.localiza_tool import LocalizaResultsDownloadTool
from app.logger import step, success

def run_crew():
    step("Montando agente CrewAI")

    agent = Agent(
        role="Agente de Automação Web",
        goal="Localizar e baixar PDFs de Divulgação de Resultados de 2026 no site RI da Localiza",
        backstory=(
            "Agente especializado em automação de navegação web, coleta de documentos "
            "financeiros e geração de relatórios técnicos com linguagem objetiva."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[LocalizaResultsDownloadTool()]
    )

    task = Task(
        description=TASK_DESCRIPTION,
        expected_output="Relatório completo da execução com evidências, downloads e observações.",
        agent=agent
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )

    step("Executando crew")
    result = crew.kickoff()

    success("Execução finalizada")
    print("\n" + "=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60)
    print(result)

