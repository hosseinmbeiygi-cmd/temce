from __future__ import annotations

import random
from collections.abc import Callable


class GeneticOptimization:
    def __init__(
        self,
        population_size: int = 50,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        generations: int = 20,
    ) -> None:
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.generations = generations

    def optimize(
        self,
        param_bounds: dict[str, tuple[float, float]],
        fitness_fn: Callable[[dict[str, float]], float],
    ) -> tuple[dict[str, float], float]:
        list(param_bounds.keys())
        population = self._init_population(param_bounds)
        best_individual: dict[str, float] = {}
        best_fitness = -1e9

        for _gen in range(self.generations):
            fitness_scores = [fitness_fn(ind) for ind in population]
            for ind, f in zip(population, fitness_scores, strict=False):
                if f > best_fitness:
                    best_fitness = f
                    best_individual = dict(ind)
            selected = self._tournament_select(population, fitness_scores)
            offspring = self._crossover(selected)
            population = self._mutate(offspring, param_bounds)

        return best_individual, best_fitness

    def _init_population(self, bounds: dict[str, tuple[float, float]]) -> list[dict[str, float]]:
        population: list[dict[str, float]] = []
        for _ in range(self.population_size):
            individual: dict[str, float] = {}
            for name, (lo, hi) in bounds.items():
                individual[name] = random.uniform(lo, hi)
            population.append(individual)
        return population

    def _tournament_select(
        self, population: list[dict[str, float]], scores: list[float], k: int = 3
    ) -> list[dict[str, float]]:
        selected: list[dict[str, float]] = []
        for _ in range(len(population)):
            contestants = random.sample(list(enumerate(scores)), min(k, len(scores)))
            winner = max(contestants, key=lambda x: x[1])[0]
            selected.append(population[winner])
        return selected

    def _crossover(self, population: list[dict[str, float]]) -> list[dict[str, float]]:
        offspring: list[dict[str, float]] = []
        for i in range(0, len(population), 2):
            p1 = population[i]
            p2 = population[(i + 1) % len(population)]
            if random.random() < self.crossover_rate:
                child1, child2 = {}, {}
                for key in p1:
                    if random.random() < 0.5:
                        child1[key] = p1[key]
                        child2[key] = p2[key]
                    else:
                        child1[key] = p2[key]
                        child2[key] = p1[key]
                offspring.extend([child1, child2])
            else:
                offspring.extend([dict(p1), dict(p2)])
        return offspring[: len(population)]

    def _mutate(
        self, population: list[dict[str, float]], bounds: dict[str, tuple[float, float]]
    ) -> list[dict[str, float]]:
        for individual in population:
            for key, (lo, hi) in bounds.items():
                if random.random() < self.mutation_rate:
                    individual[key] = random.uniform(lo, hi)
        return population
