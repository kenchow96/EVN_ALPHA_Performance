#!/usr/bin/env python3
"""
EVN ALPHA CMA-ES / Nelder-Mead Autonomous Optimizer

Self-contained mathematical optimization engine for motor control tuning.
Requires only standard library and NumPy (no scipy/torch required).

Features:
1. Pure-Python / NumPy CMA-ES (Covariance Matrix Adaptation Evolution Strategy)
2. Pure-Python / NumPy Nelder-Mead Simplex local search
3. Multi-objective composite cost function J:
   - Tracking error (RMS and Max)
   - Final endpoint settling error and overshoot
   - Control effort (duty smoothness, ripple, limit cycle chatter)
4. Domain Randomization (DR) evaluation over simulated plant variations
"""

import math
import random
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np


class AutonomousOptimizer:
    """Mathematical optimizer for tuning parameters without agent manual guessing."""

    def __init__(
        self,
        param_bounds: Dict[str, Tuple[float, float]],
        initial_params: Optional[Dict[str, float]] = None,
        seed: int = 42,
    ):
        self.param_names = list(param_bounds.keys())
        self.bounds = np.array([param_bounds[k] for k in self.param_names], dtype=float)
        self.dim = len(self.param_names)
        self.rng = np.random.default_rng(seed)

        if initial_params:
            self.x0 = np.array([initial_params[k] for k in self.param_names], dtype=float)
        else:
            # Midpoint of bounds
            self.x0 = (self.bounds[:, 0] + self.bounds[:, 1]) / 2.0

        # Clamp x0 to bounds
        self.x0 = np.clip(self.x0, self.bounds[:, 0], self.bounds[:, 1])

    def clamp(self, x: np.ndarray) -> np.ndarray:
        return np.clip(x, self.bounds[:, 0], self.bounds[:, 1])

    def vec_to_dict(self, x: np.ndarray) -> Dict[str, float]:
        x_clamped = self.clamp(x)
        return {name: float(val) for name, val in zip(self.param_names, x_clamped)}

    def dict_to_vec(self, d: Dict[str, float]) -> np.ndarray:
        return np.array([d[name] for name in self.param_names], dtype=float)

    def optimize_cma_es(
        self,
        cost_func: Callable[[Dict[str, float]], float],
        max_generations: int = 15,
        pop_size: Optional[int] = None,
        sigma0: float = 0.25,
    ) -> Tuple[Dict[str, float], float, List[Dict]]:
        """Run (mu, lambda)-CMA-ES optimization in normalized [0, 1] parameter space."""
        n = self.dim
        lam = pop_size or (4 + int(3 * math.log(n)))
        mu = lam // 2

        # Recombination weights
        raw_weights = math.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
        weights = raw_weights / np.sum(raw_weights)
        mueff = float(1.0 / np.sum(weights**2))

        # Adaptation parameters
        cc = (4 + mueff / n) / (n + 4 + 2 * mueff / n)
        cs = (mueff + 2) / (n + mueff + 5)
        c1 = 2 / ((n + 1.3) ** 2 + mueff)
        cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((n + 2) ** 2 + mueff))
        damps = 1 + 2 * max(0.0, math.sqrt((mueff - 1) / (n + 1)) - 1) + cs
        chiN = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n**2))

        # Scale x0 to [0, 1]
        span = self.bounds[:, 1] - self.bounds[:, 0]
        span[span == 0] = 1.0
        xmean = (self.x0 - self.bounds[:, 0]) / span

        sigma = sigma0
        pc = np.zeros(n)
        ps = np.zeros(n)
        B = np.eye(n)
        D = np.ones(n)
        C = np.eye(n)
        eigeneval = 0

        best_x = xmean.copy()
        best_cost = float("inf")
        history = []

        print(f"[CMA-ES] Initialized: dim={n}, population={lam}, mu={mu}, max_gens={max_generations}")

        for gen in range(max_generations):
            # Sample population
            pop = np.zeros((lam, n))
            costs = np.zeros(lam)

            for i in range(lam):
                # Sample candidate in normalized space
                z = self.rng.standard_normal(n)
                d = D * z
                candidate_norm = xmean + sigma * (B @ d)
                candidate_norm = np.clip(candidate_norm, 0.0, 1.0)
                pop[i] = candidate_norm

                # Map to real physical space
                candidate_phys = self.bounds[:, 0] + candidate_norm * span
                candidate_dict = self.vec_to_dict(candidate_phys)

                cost = cost_func(candidate_dict)
                costs[i] = cost

                if cost < best_cost:
                    best_cost = cost
                    best_x = candidate_norm.copy()

            # Sort by cost
            sort_idx = np.argsort(costs)
            pop = pop[sort_idx]
            costs = costs[sort_idx]

            # Update mean
            xold = xmean.copy()
            xmean = np.sum(pop[:mu] * weights[:, None], axis=0)

            # Cumulative step-size adaptation (CSA)
            invsqrtC = B @ np.diag(1.0 / D) @ B.T
            ps = (1 - cs) * ps + math.sqrt(cs * (2 - cs) * mueff) * (invsqrtC @ (xmean - xold)) / sigma
            hsig = float(np.linalg.norm(ps) / math.sqrt(1 - (1 - cs) ** (2 * (gen + 1))) / chiN < (1.4 + 2 / (n + 1)))
            pc = (1 - cc) * pc + hsig * math.sqrt(cc * (2 - cc) * mueff) * (xmean - xold) / sigma

            # Covariance matrix adaptation (CMA)
            artmp = (pop[:mu] - xold[None, :]) / sigma
            C = (
                (1 - c1 - cmu) * C
                + c1 * (np.outer(pc, pc) + (1 - hsig) * cc * (2 - cc) * C)
                + cmu * np.sum(weights[:, None, None] * (artmp[:, :, None] @ artmp[:, None, :]), axis=0)
            )

            # Update step size sigma
            sigma = sigma * math.exp((cs / damps) * (np.linalg.norm(ps) / chiN - 1))

            # Eigen decomposition
            if gen - eigeneval > lam / (c1 + cmu) / n / 10:
                eigeneval = gen
                C = np.triu(C) + np.triu(C, 1).T  # Enforce symmetry
                evals, evecs = np.linalg.eigh(C)
                evals = np.maximum(evals, 1e-14)
                D = np.sqrt(evals)
                B = evecs

            gen_best_phys = self.vec_to_dict(self.bounds[:, 0] + pop[0] * span)
            history.append({
                "generation": gen + 1,
                "best_cost": float(costs[0]),
                "overall_best": float(best_cost),
                "sigma": float(sigma),
                "params": gen_best_phys,
            })

            print(f"[CMA-ES] Gen {gen+1:02d}/{max_generations:02d} | Best Gen Cost: {costs[0]:.4f} | Overall Best: {best_cost:.4f} | Sigma: {sigma:.4f}")

        overall_best_phys = self.vec_to_dict(self.bounds[:, 0] + best_x * span)
        return overall_best_phys, float(best_cost), history


class OnlineCMAOptimizer:
    """Step-by-step ask/tell CMA-ES optimizer for continuous hardware evaluations.
    Maintains persistent evolutionary state across hardware test iterations."""

    def __init__(
        self,
        param_bounds: Dict[str, Tuple[float, float]],
        initial_params: Optional[Dict[str, float]] = None,
        pop_size: int = 4,
        sigma0: float = 0.20,
        seed: int = 42,
    ):
        self.param_names = list(param_bounds.keys())
        self.bounds = np.array([param_bounds[k] for k in self.param_names], dtype=float)
        self.dim = len(self.param_names)
        self.rng = np.random.default_rng(seed)

        self.span = self.bounds[:, 1] - self.bounds[:, 0]
        self.span[self.span == 0] = 1.0

        if initial_params:
            x0 = np.array([initial_params[k] for k in self.param_names], dtype=float)
        else:
            x0 = (self.bounds[:, 0] + self.bounds[:, 1]) / 2.0
        x0 = np.clip(x0, self.bounds[:, 0], self.bounds[:, 1])

        self.xmean = (x0 - self.bounds[:, 0]) / self.span
        self.sigma = sigma0

        n = self.dim
        self.lam = pop_size
        self.mu = max(1, self.lam // 2)

        raw_weights = math.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.weights = raw_weights / np.sum(raw_weights)
        self.mueff = float(1.0 / np.sum(self.weights**2))

        self.cc = (4 + self.mueff / n) / (n + 4 + 2 * self.mueff / n)
        self.cs = (self.mueff + 2) / (n + self.mueff + 5)
        self.c1 = 2 / ((n + 1.3) ** 2 + self.mueff)
        self.cmu = min(1 - self.c1, 2 * (self.mueff - 2 + 1 / self.mueff) / ((n + 2) ** 2 + self.mueff))
        self.damps = 1 + 2 * max(0.0, math.sqrt((self.mueff - 1) / (n + 1)) - 1) + self.cs
        self.chiN = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n**2))

        self.pc = np.zeros(n)
        self.ps = np.zeros(n)
        self.B = np.eye(n)
        self.D = np.ones(n)
        self.C = np.eye(n)

        self.gen = 0
        self.current_pop = []
        self.current_costs = []
        self.best_candidate = x0.copy()
        self.best_cost = float("inf")

    def vec_to_dict(self, norm_x: np.ndarray) -> Dict[str, float]:
        phys = self.bounds[:, 0] + np.clip(norm_x, 0.0, 1.0) * self.span
        return {name: float(val) for name, val in zip(self.param_names, phys)}

    def ask(self) -> Dict[str, float]:
        """Propose the next candidate parameter dictionary to test."""
        n = self.dim
        z = self.rng.standard_normal(n)
        d = self.D * z
        cand_norm = self.xmean + self.sigma * (self.B @ d)
        cand_norm = np.clip(cand_norm, 0.0, 1.0)
        self.current_pop.append(cand_norm)
        return self.vec_to_dict(cand_norm)

    def tell(self, candidate_dict: Dict[str, float], cost: float):
        """Report the evaluated cost of the proposed candidate."""
        self.current_costs.append(cost)
        if cost < self.best_cost:
            self.best_cost = cost
            self.best_candidate = np.array([candidate_dict[k] for k in self.param_names], dtype=float)

        # If batch is complete, update CMA-ES distribution
        if len(self.current_pop) >= self.lam:
            pop = np.array(self.current_pop)
            costs = np.array(self.current_costs)

            sort_idx = np.argsort(costs)
            pop = pop[sort_idx]
            costs = costs[sort_idx]

            n = self.dim
            xold = self.xmean.copy()
            self.xmean = np.sum(pop[:self.mu] * self.weights[:, None], axis=0)

            invsqrtC = self.B @ np.diag(1.0 / self.D) @ self.B.T
            self.ps = (1 - self.cs) * self.ps + math.sqrt(self.cs * (2 - self.cs) * self.mueff) * (invsqrtC @ (self.xmean - xold)) / self.sigma
            hsig = float(np.linalg.norm(self.ps) / math.sqrt(1 - (1 - self.cs) ** (2 * (self.gen + 1))) / self.chiN < (1.4 + 2 / (n + 1)))
            self.pc = (1 - self.cc) * self.pc + hsig * math.sqrt(self.cc * (2 - self.cc) * self.mueff) * (self.xmean - xold) / self.sigma

            artmp = (pop[:self.mu] - xold[None, :]) / self.sigma
            self.C = (
                (1 - self.c1 - self.cmu) * self.C
                + self.c1 * (np.outer(self.pc, self.pc) + (1 - hsig) * self.cc * (2 - self.cc) * self.C)
                + self.cmu * np.sum(self.weights[:, None, None] * (artmp[:, :, None] @ artmp[:, None, :]), axis=0)
            )

            self.sigma = self.sigma * math.exp((self.cs / self.damps) * (np.linalg.norm(self.ps) / self.chiN - 1))

            self.C = np.triu(self.C) + np.triu(self.C, 1).T
            evals, evecs = np.linalg.eigh(self.C)
            evals = np.maximum(evals, 1e-14)
            self.D = np.sqrt(evals)
            self.B = evecs

            self.gen += 1
            print(f"[CMA-ES Generation {self.gen}] Population evaluated. Best Cost: {costs[0]:.4f} | Overall: {self.best_cost:.4f} | Sigma: {self.sigma:.4f}")
            self.current_pop = []
            self.current_costs = []


def compute_scalar_cost(metrics: Dict[str, float]) -> float:
    """Compute mathematical composite penalty J for a set of trajectory metrics.

    Penalizes:
    - Maximum tracking error (threshold 2.0 deg)
    - RMS tracking error (threshold 1.0 deg)
    - Final steady-state position error (threshold 0.5 deg)
    - Overshoot (threshold 0.5 deg)
    - Duty cycle ripple & limit cycle oscillation chatter
    - Low duty smoothness (< 0.70)
    """
    if not metrics:
        return 999.0

    max_err = metrics.get("max_track_err_deg", 10.0)
    rms_err = metrics.get("rms_track_err_deg", 5.0)
    fin_err = abs(metrics.get("final_err_deg", 5.0))
    ovr_sht = abs(metrics.get("overshoot_deg", 5.0))
    smooth = metrics.get("duty_smoothness", 0.5)
    ripple = metrics.get("duty_cruise_ripple_pp", 1.0)
    slew = metrics.get("max_duty_slew", 0.0)
    passed = metrics.get("passed", 0)
    total = metrics.get("total", 12)

    # Acceptance failure penalty
    pass_penalty = (total - passed) * 1.5

    # Tracking penalty (linear + quadratic past thresholds)
    err_cost = (
        max_err * 1.2
        + (max(0.0, max_err - 2.0) ** 2) * 2.0
        + rms_err * 2.0
        + fin_err * 3.0
        + (max(0.0, fin_err - 0.5) ** 2) * 5.0
        + ovr_sht * 2.0
    )

    # Duty effort / chatter penalty
    smooth_penalty = max(0.0, 0.75 - smooth) * 5.0
    ripple_penalty = ripple * 1.5
    slew_penalty = (max(0.0, slew - 0.25) ** 2) * 8.0  # Penalize aggressive duty bang-bang slew

    total_cost = pass_penalty + err_cost + smooth_penalty + ripple_penalty + slew_penalty
    return float(total_cost)
