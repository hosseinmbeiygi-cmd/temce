from scripts.bootstrap_env import bootstrap as bootstrap_environment

# ``bootstrap_environment`` is kept as an alias for backward compatibility.
bootstrap = bootstrap_environment

__all__ = ["bootstrap", "bootstrap_environment"]
