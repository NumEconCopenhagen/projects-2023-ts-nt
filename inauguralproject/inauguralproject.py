
from types import SimpleNamespace

import numpy as np
from scipy import optimize

import pandas as pd
import matplotlib.pyplot as plt

class HouseholdSpecializationModelClass:

    def __init__(self):
        """ setup model """

        # a. create namespaces
        par = self.par = SimpleNamespace()
        sol = self.sol = SimpleNamespace()

        # b. preferences
        par.rho = 2.0
        par.nu = 0.001
        par.epsilon = 1.0
        par.omega = 0.5

        # c. household production
        par.alpha = 0.5
        par.sigma = 1.0

        # d. wages
        par.wM = 1.0
        par.wF = 1.0
        par.wF_vec = np.linspace(0.8,1.2,5)

        # e. targets
        par.beta0_target = 0.4
        par.beta1_target = -0.1

        # f. solution
        sol.LM_vec = np.zeros(par.wF_vec.size)
        sol.HM_vec = np.zeros(par.wF_vec.size)
        sol.LF_vec = np.zeros(par.wF_vec.size)
        sol.HF_vec = np.zeros(par.wF_vec.size)

        sol.beta0 = np.nan
        sol.beta1 = np.nan

    def calc_utility(self,LM,HM,LF,HF):
        """ calculate utility """

        par = self.par
        sol = self.sol

        # a. consumption of market goods
        C = par.wM*LM + par.wF*LF

        # b. home production
        if par.sigma == 1:
            H = HM**(1-par.alpha)*HF**par.alpha
        elif par.sigma == 0:
            H = min(HM, HF)
        else :
            H = ((1-par.alpha)*HM**((par.sigma-1)/par.sigma) + par.alpha*HF**((par.sigma-1)/par.sigma))**(par.sigma/(par.sigma-1))

        # c. total consumption utility
        Q = C**par.omega*H**(1-par.omega)
        utility = np.fmax(Q,1e-8)**(1-par.rho)/(1-par.rho)

        # d. disutlity of work
        epsilon_ = 1+1/par.epsilon
        TM = LM+HM
        TF = LF+HF
        disutility = par.nu*(TM**epsilon_/epsilon_+TF**epsilon_/epsilon_)
        
        return utility - disutility

    def solve_discrete(self,do_print=False):
        """ solve model discretely """
        
        par = self.par
        sol = self.sol
        opt = SimpleNamespace()
        
        # a. all possible choices
        x = np.linspace(0,24,49)
        LM,HM,LF,HF = np.meshgrid(x,x,x,x) # all combinations
    
        LM = LM.ravel() # vector
        HM = HM.ravel()
        LF = LF.ravel()
        HF = HF.ravel()

        # b. calculate utility
        u = self.calc_utility(LM,HM,LF,HF)
    
        # c. set to minus infinity if constraint is broken
        I = (LM+HM > 24) | (LF+HF > 24) # | is "or"
        u[I] = -np.inf
    
        # d. find maximizing argument
        j = np.argmax(u)
        
        opt.LM = LM[j]
        opt.HM = HM[j]
        opt.LF = LF[j]
        opt.HF = HF[j]
        
        return opt

    def solve(self,do_print=False):
        """ solve model continously """
        
        par = self.par
        sol = self.sol
        opt = SimpleNamespace()

        # a. define negative utility function
        def neg_utility(x):
            LM,HM,LF,HF = x
            return -self.calc_utility(LM,HM,LF,HF)

        # b. define constraints
        def constraint1(x):
            LM,HM,LF,HF = x
            return 24 - (LM+HM)
        def constraint2(x):
            LM,HM,LF,HF = x
            return 24 - (LF+HF)
        constraints = [{'type': 'ineq', 'fun': constraint1},
                        {'type': 'ineq', 'fun': constraint2}]

        # c. initial guess
        x0 = np.array([12, 12, 12, 12])

        # d. solve optimization problem
        result = optimize.minimize(neg_utility, x0, constraints=constraints)

        # e. save solution
        opt.LM = result.x[0]
        opt.HM = result.x[1]
        opt.LF = result.x[2]
        opt.HF = result.x[3]

        return opt  

    def solve_wF_vec(self,discrete=False):
        """ solve model for vector of female wages """
        
        par = self.par
        sol = self.sol
        opt = SimpleNamespace()
        
        if discrete:
            # a. solve model discretely for each wage
            for i, wF in enumerate(par.wF_vec):
                par.wF = wF
                sol_i = self.solve_discrete()
                sol.LM_vec[i] = sol_i.LM
                sol.HM_vec[i] = sol_i.HM
                sol.LF_vec[i] = sol_i.LF
                sol.HF_vec[i] = sol_i.HF
        else:
            # b. solve model continously for each wage
            def fun(x):
                LF, HF = x
                u = -self.calc_utility(par.LM, par.HM, LF, HF)
                return u
            for i, wF in enumerate(par.wF_vec):
                par.wF = wF
                par.LM = sol.LM_vec[i]
                par.HM = sol.HM_vec[i]
                LF, HF = optimize.minimize(fun, [sol.LF_vec[i], sol.HF_vec[i]]).x
                sol.LF_vec[i] = LF
                sol.HF_vec[i] = HF
        
        return opt

    def run_regression(self):
        """ run regression """

        par = self.par
        sol = self.sol

        x = np.log(par.wF_vec)
        y = np.log(sol.HF_vec/sol.HM_vec)
        A = np.vstack([np.ones(x.size),x]).T
        sol.beta0,sol.beta1 = np.linalg.lstsq(A,y,rcond=None)[0]
    
    def estimate(self,alpha=None,sigma=None):
        """ estimate alpha and sigma """

        par = self.par
        sol = self.sol
        opt = SimpleNamespace()

        # a. define function to fit
        def func(x,alpha,sigma):
            HF_over_HM = np.exp(alpha*np.log(x) + sigma/2*np.log(1+(1/alpha)*(x**(1-alpha)-1)))
            return HF_over_HM
    
        # b. get data
        x = par.wF_vec
        y = sol.HF_vec/sol.HM_vec

        # c. estimate parameters
        if alpha is None:
            alpha = par.alpha
        if sigma is None:
            sigma = par.sigma

        
        # d. save results
        par.alpha = opt[0]
        par.sigma = opt[1]

        return opt
