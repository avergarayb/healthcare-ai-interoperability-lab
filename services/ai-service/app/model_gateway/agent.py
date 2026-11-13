"""Use-case agent. It knows the gateway, not a provider SDK or a graph state."""


class VacationClauseAgent:
    def __init__(self, gateway):
        self._gateway = gateway

    def run(self, context, grant):
        return self._gateway.execute(context, grant)
