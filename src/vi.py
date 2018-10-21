import torch
from torch import nn
from torch import digamma
from torch.distributions import MultivariateNormal as MVN
from torch.distributions import Bernoulli as Bern
from utils import register_hooks, visualize_A

import math
LOG_2PI = 1.8378770664093453

EPS = 1e-16

# class FiniteIBP(nn.Module):
#     """

#     Finite/Truncated Approximation of the Indian Buffet Process
#     with mean-field variational posterior approximation.
#     Section 4 in http://mlg.eng.cam.ac.uk/pub/pdf/DosMilVanTeh09b.pdf

#     Generative Model:
#     pi_k ~ Beta(alpha/K,1)            for k in {1,...,K}
#     z_nk ~ Bernoulli(pi_k)            for k in {1,...,K}, n in {1,...,N}
#     A_k ~ Normal(0, sigma_a^2 I)      for k in {1,...,K}
#     X_n ~ Normal(Z_n A, sigma_n^2 I)  for n in {1,...,N}

#     Variational Distributions:
#     q(pi_k) = Beta(pi_k;tau_k1,tau_k2)
#     q(A_k) = Normal(A_k;phi_k,phi_var_k)
#     q(z_nk) = Bernoulli(z_nk;nu_nk)

#     NOTE: must call init_z with a given N to start.
#     TODO: this model isn't finished (because we're working on the InfiniteIBP)
#     """
#     def __init__(self, alpha, K, sigma_a, sigma_n, D):
#         # idempotent - all are constant and have requires_grad=True
#         self.alpha = torch.tensor(alpha)
#         self.K = torch.tensor(K)
#         self.sigma_a = torch.tensor(sigma_a)
#         self.sigma_n = torch.tensor(sigma_n)
#         self.D = torch.tensor(D)

#         # we don't know N, but we'll still initialize everything else
#         self.init_variables()

#     def init_variables(N=100):
#         self.tau = nn.Parameter(torch.rand(self.K, 2))
#         self.phi = nn.Parameter(torch.randn(self.K, self.D))
#         self.phi_var = nn.Parameter(torch.zeros(self.K, self.D, self.D))
#         for k in self.K:
#             self.phi_var[k] = torch.eye(self.D)

#     def init_z(N=100):
#         self.nu = nn.Parameter(torch.rand(N, self.K))

#     def elbo(X):
#         """
#         This is the evidence lower bound evaluated at X, when X is of shape (N, D)
#         i.e. log p_K(X | theta) \geq ELBO
#         """
#         return self._1_feature_prob(self.tau).sum() + \
#                self._2_feature_assign(self.nu, self.tau).sum() + \
#                self._3_feature_prob(self.phi_var, self.phi).sum() + \
#                self._4_likelihood(X, self.nu, self.phi_var, self.phi) + \
#                self._5_entropy(self.tau, self.phi_var, self.nu)

#     def _1_feature_prob(self, tau):
#         """
#         @param tau: (K, 2)
#         @return: (K,)

#         Computes Cross Entropy: E_q(pi) [logp(pi_k|alpha)]
#         """
#         return self.alpha.log() - self.K.log() + (self.alpha/self.K - 1) * \
#             (digamma(tau[:, 0]) - digamma(tau.sum(dim=1)))

#     def _2_feature_assign(self, nu, tau):
#         """
#         @param nu: (N, K)
#         @param tau: (K, 2)
#         @return: (N, K)

#         Computes Cross Entropy: E_q(pi),q(Z) [logp(z_nk|pi_k)]
#         """
#         return nu * digamma(tau[:, 0]) + (1. - nu) * digamma(tau[:, 1]) - digamma(tau.sum(dim=1))

#     def _3_feature_prob(self, phi_var, phi):
#         """
#         @param phi_var: (K, D, D)
#         @param phi: (K, D)
#         @return: ()

#         NOTE: must return () because torch.trace doesn't allow specifying axes

#         Computes Cross Entropy: E_q(A) [logp(A_k|sigma_a^2 I)]
#         """
#         ret = 0
#         constant = -0.5 * self.D * (self.sigma_a.log() + LOG_2PI)
#         for k in range(self.K):
#             other_term = (-0.5 / (self.sigma_a**2)) * \
#                 (torch.trace(phi_var[k]) + phi[k].pow(2).sum())
#             ret += constant + other_term

#     def _4_likelihood(self, X, nu, phi_var, phi):
#         """
#         @param X: (N, D)
#         @param nu: (N, K)
#         @param phi_var: (K, D, D)
#         @param phi: (K, D)
#         @return: ()

#         Computes Likelihood: E_q(Z),q(A) [logp(X_n|Z_n,A,sigma_n^2 I)]
#         """
#         N, _ = X.shape
#         K, D = self.K, self.D # for notational simplicity
#         ret = 0
#         constant = -0.5 * D * (self.sigma_n.log() + LOG_2PI)

#         first_term = X.pow(2).sum()
#         second_term = (-2 * (nu.view(N, K, 1) * phi.view(1, K, D)) * X.view(1, K, D)).sum()
#         third_term = 2 * torch.triu((phi @ phi.transpose(0, 1)) * \
#                 (nu.transpose(0, 1) @ nu), diagonal=1).sum()

#         # have to loop because of torch.trace again
#         fourth_term = 0
#         for k in range(K):
#             fourth_term += (nu[:, k] * (torch.trace(phi_var[k]) + phi[k].pow(2).sum())).sum()

#         nonconstant = (-0.5/(self.sigma_n**2)) * \
#             (first_term + second_term + third_term + fourth_term)

#         return constant + nonconstant

#     def _5_entropy(self, tau, phi_var, nu):
#         """
#         @param tau: (K, 2)
#         @param phi_var: (K, D, D)
#         @param nu: (N, K)
#         @return: ()

#         Computes Entropy H[q] for all variational distributions q
#         """
#         entropy_q_pi = (tau.lgamma().sum(1) - tau.sum(1).lgamma() - \
#             (tau[:, 0] - 1) * digamma(tau[:, 0]) - \
#             (tau[:, 1] - 1) * digamma(tau[:, 1]) + \
#             (tau.sum(1) - 2.) * digamma(tau.sum(1))).sum()
#         entropy_q_A = 0
#         for k in self.K:
#             entropy_q_A += 0.5 * (self.D * (1 + LOG_2PI) + torch.logdet(phi_var[k])).sum()
#         entropy_q_z = -(nu * nu.log() + (1 - nu) * (1 - nu).log()).sum()
#         return entropy_q_pi + entropy_q_A + entropy_q_z

# imports to make Jeffrey's code work
import numpy as np
import numpy.random as npr
from numpy.random import beta
import scipy.special as sps
from scipy.special import gamma, gammaln, logsumexp
from numpy.linalg import slogdet

class InfiniteIBP(nn.Module):
    """
    Infinite/Non-Truncated Indian Buffet Process
    with a mean-field variational posterior approximation.
    Section 5 in http://mlg.eng.cam.ac.uk/pub/pdf/DosMilVanTeh09b.pdf

    Generative Model:
    v_k ~ Beta(alpha,1)               for k in {1,...,inf}
    pi_k = product_{i=1}^k v_i        for k in {1,...,inf}
    z_nk ~ Bernoulli(pi_k)            for k in {1,...,inf}, n in {1,...,N}
    A_k ~ Normal(0, sigma_a^2 I)      for k in {1,...,inf}
    X_n ~ Normal(Z_n A, sigma_n^2 I)  for n in {1,...,N}

    q(v_k) = Beta(v_k;tau_k1,tau_k2 (now over v rather than pi)
    q(A_k) = Normal(A_k;phi_k,phi_var_k)
    q(z_nk) = Bernoulli(z_nk; nu_nk)

    In truncated stick breaking for the infinite model,
    pi_k = product_{i=1}^k v_i for k <= K and zero otherwise.

    NOTE: must call init_z with a given N to start.
    """
    def __init__(self, alpha, K, sigma_a, sigma_n, D):
        super(InfiniteIBP, self).__init__()

        # idempotent - all are constant and have requires_grad=True
        self.alpha = torch.tensor(alpha)
        self.K = torch.tensor(K)
        self.sigma_a = torch.tensor(sigma_a)
        self.sigma_n = torch.tensor(sigma_n)
        self.D = torch.tensor(D)

        # we don't know N, but we'll still initialize everything else
        self.init_variables()

    def init_variables(self, N=100):
        # NOTE: tau must be positive, so we use the @property below
        self._tau = nn.Parameter(torch.rand(self.K, 2))
        self.phi = nn.Parameter(torch.randn(self.K, self.D))
        self._phi_var = torch.zeros(self.K, self.D, self.D)
        for k in range(self.K):
            self._phi_var[k] = torch.eye(self.D)
        self._phi_var = nn.Parameter(self._phi_var) # must create nn.Parameter after updates

    """
    Note we use the following trick for sweeping the constraint parametrization
    'under the rug' so to speak - whenever we access self.tau, we get the
    constrained-to-be-positive version
    """

    @property
    def tau(self):
        return 1. + nn.Softplus()(self._tau)

    @property
    def nu(self):
        return nn.Sigmoid()(self._nu)

    @property
    def phi_var(self):
        return nn.Softplus()(self._phi_var)

    def init_z(self, N=100):
        self._nu = nn.Parameter(torch.rand(N, self.K))

    def elbo(self, X):
        """
        This is the evidence lower bound evaluated at X, when X is of shape (N, D)
        i.e. log p_K(X | theta) \geq ELBO
        """
        a = self._1_feature_prob(self.tau).sum()
        b = self._4_likelihood(X, self.nu, self.phi_var, self.phi).sum()
        c = self._2_feature_assign(self.nu, self.tau).sum()
        d = self._3_feature_prob(self.phi_var, self.phi).sum()
        e = self._5_entropy(self.tau, self.phi_var, self.nu).sum()
        print(a.item() < 0, b.item() < 0, c.item() < 0, d.item() < 0, e.item() > 0)
        print((b + c + d + e).item() > 0)
        return a + b + c + d + e

    def _1_feature_prob(self, tau):
        """
        @param tau: (K, 2)
        @return: (K,)

        Computes Cross Entropy: E_q(v) [logp(v_k|alpha)]
        """
        return self.alpha.log() + \
            ((self.alpha - 1) * (digamma(tau[:, 0]) - digamma(tau.sum(dim=1))))

    def jeffrey_compute_q_Elogstick(tau, k):
        tau = tau.T
        # k = k + 1 # length
        digamma1 = np.array([sps.digamma(tau[0][i]) for i in range(k)])
        digamma2 = np.array([sps.digamma(tau[1][i]) for i in range(k)])
        digamma12 = np.array([sps.digamma(tau[0][i] + tau[1][i]) for i in range(k)])

        # initialize q distribution
        lqs = np.array([digamma2[i] + sum(digamma1[:i-1]) - sum(digamma12[:i]) for i in range(k)])
        lqs[0] = digamma2[0] - digamma12[0] # dumb indexing fix
        q_partition = logsumexp(lqs)
        qs = np.exp(lqs - q_partition)
        q_tails = [qs[-1]]
        for m in range(k-2, -1, -1):
            q_tails.append(qs[m] + q_tails[-1])
        q_tails.reverse()

        Elogstick = np.sum(qs * digamma2)
        Elogstick += sum([digamma1[m] * q_tails[m+1] for m in range(k-1)])
        Elogstick += -sum([digamma12[m] * q_tails[m] for m in range(k)])
        Elogstick += - np.sum(qs * np.log(qs))

        # return
        return qs , Elogstick

    def _E_log_stick(self, tau):
        """
        @param tau: (K, 2)
        @return: ((K,), (K, K))

        where the first return value is E_log_stick, and the second is q
        """
        np.set_printoptions(precision=2, suppress=True)
        # let's compute the distribution by hand
        hand_q = np.zeros(2)
        taud = tau.clone().detach().numpy()
        from scipy.special import digamma as dgm
        hand_q[0] = dgm(taud[0, 1]) - dgm(taud[0, 1] + taud[0, 0])
        hand_q[1] = dgm(taud[1, 1]) + dgm(taud[0, 0]) - \
            (dgm(taud[0, 0] + taud[0, 1]) + dgm(taud[1, 0] + taud[1, 1]))
        # print(hand_q)
        a = np.exp(hand_q)
        print("hand computed q (k=2):")
        print(a/a.sum())

        # we use the same indexing as in eq. (10)
        q = torch.zeros(self.K, self.K)

        # working in log space until the last step
        first_term = digamma(tau[:, 1])
        second_term = digamma(tau[:, 0]).cumsum(0) - digamma(tau[:, 0])
        third_term = digamma(tau.sum(1)).cumsum(0)
        # print(first_term.detach().numpy())
        # print(second_term.detach().numpy())
        # print(third_term.detach().numpy())
        q += (first_term + second_term - third_term).view(1, -1)
        # print(q)
        q = torch.tril(q.exp())
        q = torch.nn.functional.normalize(q, p=1, dim=1)
        # TODO: should we detach q? what does that do to the ADVI?

        # each vector should be size (K,)
        first = (q * digamma(tau[:, 1]).view(1, -1)).sum(1)
        second = ((1 - q.cumsum(1)) * tau[:, 1]).sum(1)
        third = ((1 - q.cumsum(1) - q) * tau.sum(1)).sum(1)
        temp_q = q.clone() # TODO: why clone?
        temp_q[q == 0] = 1. # since half of q is 0, log(1) is now a mask
        fourth = (temp_q * (temp_q + EPS).log()).sum(1)
        torch_e_logstick = first + second + third + fourth

        # return torch_e_logstick, q
        #
        # run Jeffrey's code
        #
        tau = tau.detach().numpy().T
        k = 2
        digamma1 = np.array([sps.digamma(tau[0][i]) for i in range(k)])
        digamma2 = np.array([sps.digamma(tau[1][i]) for i in range(k)])
        digamma12 = np.array([sps.digamma(tau[0][i] + tau[1][i]) for i in range(k)])

        # initialize q distribution
        lqs = np.array([digamma2[i] + sum(digamma1[:i-1]) - sum(digamma12[:i]) for i in range(k)])
        lqs[0] = digamma2[0] - digamma12[0] # dumb indexing fix
        q_partition = logsumexp(lqs)
        qs = np.exp(lqs - q_partition)
        q_tails = [qs[-1]]
        for m in range(k-2, -1, -1):
            q_tails.append(qs[m] + q_tails[-1])
        q_tails.reverse()

        print("our version (for all k):")
        print(q.detach().numpy())
        print("Jeffrey's compute_q_Elogstick (for k=2)")
        print(qs)
        import pdb; pdb.set_trace()

        Elogstick = np.sum(qs * digamma2)
        Elogstick += sum([digamma1[m] * q_tails[m+1] for m in range(k-1)])
        Elogstick += -sum([digamma12[m] * q_tails[m] for m in range(k)])
        Elogstick += - np.sum(qs * np.log(qs))

        # return
        return qs , Elogstick

    def _2_feature_assign(self, nu, tau):
        """
        @param nu: (N, K)
        @param tau: (K, 2)
        @return: (N, K)

        Computes Cross Entropy: E_q(v),q(Z) [logp(z_nk|v)]
        """
        return (nu * (digamma(tau[:,1]) - digamma(tau.sum(dim=1))).cumsum(0) + \
            (1. - nu) * self._E_log_stick(tau)[0])

    def _3_feature_prob(self, phi_var, phi):
        """
        @param phi_var: (K, D, D)
        @param phi: (K, D)
        @return: ()

        NOTE: must return () because torch.trace doesn't allow specifying axes

        Computes Cross Entropy: E_q(A) [logp(A_k|sigma_a^2 I)]
        Same as Finite Approach
        """
        ret = 0
        constant = -0.5 * self.D * (2 * self.sigma_a.log() + LOG_2PI)
        for k in range(self.K):
            other_term = (-0.5 / (self.sigma_a**2)) * \
                (torch.trace(phi_var[k]) + phi[k].pow(2).sum())
            ret += constant + other_term
        return ret

    def _4_likelihood(self, X, nu, phi_var, phi):
        """
        @param X: (N, D)
        @param nu: (N, K)
        @param phi_var: (K, D, D)
        @param phi: (K, D)
        @return: ()

        Computes Likelihood: E_q(Z),q(A) [logp(X_n|Z_n,A,sigma_n^2 I)]
        Same as Finite Approach
        """
        N, _ = X.shape
        K, D = self.K, self.D # for notational simplicity
        ret = 0
        constant = -0.5 * D * (self.sigma_n.log() + LOG_2PI)

        first_term = X.pow(2).sum()
        second_term = (-2 * (nu.view(N, K, 1) * phi.view(1, K, D)) * X.view(N, 1, D)).sum()
        third_term = 2 * torch.triu((phi @ phi.transpose(0, 1)) * \
                (nu.transpose(0, 1) @ nu), diagonal=1).sum()

        # have to loop because of torch.trace again
        fourth_term = 0
        for k in range(K):
            fourth_term += (nu[:, k] * (torch.trace(phi_var[k]) + phi[k].pow(2).sum())).sum()

        nonconstant = (-0.5/(self.sigma_n**2)) * \
            (first_term + second_term + third_term + fourth_term)

        return constant + nonconstant

    def _5_entropy(self, tau, phi_var, nu):
        """
        @param tau: (K, 2)
        @param phi_var: (K, D, D)
        @param nu: (N, K)
        @return: ()

        Computes Entropy H[q] for all variational distributions q
        Same as Finite Approach, just rename entropy_q_pi to entropy_q_v.
        """
        # entropy_q_v = ((tau.lgamma().sum(1) - tau.sum(1).lgamma()) - \
            # ((tau - 1.) * digamma(tau)) .sum(1) + \
            # ((tau.sum(1) - 2.) * digamma(tau.sum(1)))).sum()
        entropy_q_v = 0
        for k in range(self.K):
            tau_1 = tau[k, 0]
            tau_2 = tau[k, 1]
            entropy_q_v += tau_1.lgamma() + tau_2.lgamma() - (tau_1 + tau_2).lgamma()
            entropy_q_v -= ((tau_1 - 1) * digamma(tau_1) + (tau_2 - 1) * digamma(tau_2))
            entropy_q_v += ((tau_1 + tau_2 - 2) * digamma(tau_1 + tau_2))
        entropy_q_A = 0
        for k in range(self.K):
            entropy_q_A += 0.5 * (self.D * (1 + LOG_2PI) + torch.logdet(phi_var[k])).sum()
        entropy_q_z = -(nu * (nu + EPS).log() + (1 - nu) * (1 - nu + EPS).log()).sum()
        print(entropy_q_v.item() > 0, entropy_q_A.item() > 0, entropy_q_z.item() > 0)
        return entropy_q_v + entropy_q_A + entropy_q_z

    def cavi(self, X):
        """
        TODO: should this function have arguments?
        There are so many dumb terms in this
        """
        N, K, D = self.N, self.K, self.D
        # update q(A)
        for k in range(K):
            precision = (1./(self.sigma_a ** 2) + self.nu[:, k].sum()/(self.sigma_n**2))
            self.phi_var[k] = torch.eye(self.D) / precision
            self.phi[k] = (nu * (X - (self.nu @ self.phi - self.nu[:, k].view((N, 1)) * \
                                                           self.phi[k].view((1, D))))).sum(0) / (self.sigma_n ** 2)
        # update q(z)
        # we shouldn't vectorize this I think (TODO: discuss)
        # Marks comment: update for nu_nk depends on nu_nl forall l != k
        # so perhaps it can be parallelized across n, but not k
        for k in range(K):
            for n in range(N):
                first_term = (digamma(tau[:k+1, 1]) - digamma(tau.sum(1)[:k+1])).sum() - \
                    self._E_log_stick(self.tau)[0][k]
                other_prod = (self.nu @ self.phi - self.nu[:, k].view((N, 1)) * self.phi[k].view((1, D)))[n]
                second_term = -0.5 / (self.sigma_n ** 2) * (torch.trace(self.phi_var[k]) + self.phi[k].pow(2).sum()) + \
                    (self.phi[k] @ (X[n] - other_prod))/ (self.sigma_n ** 2)
                self.nu[n][k] = 1./(1. + (-(first_term + second_term)).exp())

        # update q(pi)
        for k in range(K):
            q = self._E_log_stick(self.tau)[1]
            self.tau[k][0] = self.alpha + self.nu[:, k:].sum() + \
                ((N - self.nu.sum(0)) * q[:, k+1:].sum(1))[k+1:].sum()
            self.tau[k][1] = 1 + ((N - self.nu.sum(0)) * q[:, k])[k:].sum()


def fit_infinite_to_ggblocks_cavi():
    pass

def fit_infinite_to_ggblocks_advi_exact():
    from data import generate_gg_blocks, generate_gg_blocks_dataset
    N = 100
    X = generate_gg_blocks_dataset(N, 0.5)

    model = InfiniteIBP(4., 6, 0.1, 0.5, 36)
    model.init_z(N)
    model.train()

    optimizer = torch.optim.Adam(model.parameters(), 3e-2)
    for i in range(100):
        optimizer.zero_grad()
        loss = -model.elbo(X)
        print(loss.item())
        # if i == 2:
        #     get_dot = register_hooks(loss)
        loss.backward()
        # if i == 2:
            # dot = get_dot()
            # dot.save('tmp.dot')
        # print(torch.isnan(model.nu.grad).any())
        optimizer.step()
    for i in range(6):
        visualize_A(model.phi.detach().numpy()[i])

if __name__ == '__main__':
    """
    python src/vi.py will just check that the model works on a ggblocks dataset
    """
    fit_infinite_to_ggblocks_advi_exact()
