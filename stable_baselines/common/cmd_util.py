"""
Helpers for scripts like run_atari.py.
"""

import os

import gym
from gym.wrappers import FlattenDictWrapper

from stable_baselines import logger
from stable_baselines.bench import Monitor
from stable_baselines.common import set_global_seeds
from stable_baselines.common.atari_wrappers import make_atari, wrap_deepmind
from stable_baselines.common.misc_util import mpi_rank_or_zero
from stable_baselines.common.vec_env import DummyVecEnv, SubprocVecEnv


def make_vec_env(env_id, n_envs=1, seed=None, start_index=0,
                 use_subprocess=False, start_method=None,
                 monitor_path=None, wrapper_class=None, env_kwargs=None):
    """
    Create a wrapped, monitored VecEnv.

    :param env_id: (str or gym.Env) the environment ID or the environment class
    :param n_envs: (int) the number of environment you wish to have in parallel
    :param seed: (int) the inital seed for random number generator
    :param start_index: (int) start rank index
    :param start_method: (str) method used to start the subprocesses.
        See SubprocVecEnv doc for more information
    :param use_subprocess: (bool) Whether to use `SubprocVecEnv` or `DummyVecEnv` when
        `n_envs` > 1, `DummyVecEnv` is usually faster. Default: False
    :param wrapper: (gym.Wrapper) Additional wrapper to use on the environment
    :param env_kwargs: (dict) Optional keyword argument to pass to the env constructor
    :return: (VecEnv) The wrapped environment
    """
    env_kwargs = {} if env_kwargs is None else env_kwargs
    def make_env(rank):
        def _init():
            if isinstance(env_id, str):
                env = gym.make(env_id)
            else:
                env = env_id(**env_kwargs)
            if seed is not None:
                env.seed(seed)
                env.action_space.seed(seed)
            # Wrap the env in a Monitor wrapper
            # to have additional training information
            monitor_path = os.path.join(monitor_path, str(rank)) if monitor_path is not None else None
            # Create the monitor folder if needed
            if monitor_path is not None:
                os.makedirs(log_dir, exist_ok=True)
            env = Monitor(env, filename=monitor_path)
            # Optionally, wrap the environment with the provided wrapper
            if wrapper_class is not None:
                env = wrapper_class(env)
            return env
        return _init

    if seed is not None:
        set_global_seeds(seed)

    if n_envs == 1 or not use_subprocess:
        return DummyVecEnv([make_env(i + start_index) for i in range(n_envs)])

    return SubprocVecEnv([make_env(i + start_index) for i in range(n_envs)],
                         start_method=start_method)


def make_atari_env(env_id, num_env, seed, wrapper_kwargs=None,
                   start_index=0, allow_early_resets=True,
                   start_method=None, use_subprocess=True):
    """
    Create a wrapped, monitored SubprocVecEnv for Atari.

    :param env_id: (str) the environment ID
    :param num_env: (int) the number of environment you wish to have in subprocesses
    :param seed: (int) the inital seed for RNG
    :param wrapper_kwargs: (dict) the parameters for wrap_deepmind function
    :param start_index: (int) start rank index
    :param allow_early_resets: (bool) allows early reset of the environment
    :param start_method: (str) method used to start the subprocesses.
        See SubprocVecEnv doc for more information
    :param use_subprocess: (bool) Whether to use `SubprocVecEnv` or `DummyVecEnv` when
        `num_env` > 1, `DummyVecEnv` is usually faster. Default: True
    :return: (VecEnv) The atari environment
    """
    if wrapper_kwargs is None:
        wrapper_kwargs = {}

    def make_env(rank):
        def _thunk():
            env = make_atari(env_id)
            env.seed(seed + rank)
            env = Monitor(env, logger.get_dir() and os.path.join(logger.get_dir(), str(rank)),
                          allow_early_resets=allow_early_resets)
            return wrap_deepmind(env, **wrapper_kwargs)
        return _thunk
    set_global_seeds(seed)

    # When using one environment, no need to start subprocesses
    if num_env == 1 or not use_subprocess:
        return DummyVecEnv([make_env(i + start_index) for i in range(num_env)])

    return SubprocVecEnv([make_env(i + start_index) for i in range(num_env)],
                         start_method=start_method)


def make_mujoco_env(env_id, seed, allow_early_resets=True):
    """
    Create a wrapped, monitored gym.Env for MuJoCo.

    :param env_id: (str) the environment ID
    :param seed: (int) the inital seed for RNG
    :param allow_early_resets: (bool) allows early reset of the environment
    :return: (Gym Environment) The mujoco environment
    """
    set_global_seeds(seed + 10000 * mpi_rank_or_zero())
    env = gym.make(env_id)
    env = Monitor(env, os.path.join(logger.get_dir(), str(rank)), allow_early_resets=allow_early_resets)
    env.seed(seed)
    return env


def make_robotics_env(env_id, seed, rank=0, allow_early_resets=True):
    """
    Create a wrapped, monitored gym.Env for MuJoCo.

    :param env_id: (str) the environment ID
    :param seed: (int) the inital seed for RNG
    :param rank: (int) the rank of the environment (for logging)
    :param allow_early_resets: (bool) allows early reset of the environment
    :return: (Gym Environment) The robotic environment
    """
    set_global_seeds(seed)
    env = gym.make(env_id)
    env = FlattenDictWrapper(env, ['observation', 'desired_goal'])
    env = Monitor(
        env, logger.get_dir() and os.path.join(logger.get_dir(), str(rank)),
        info_keywords=('is_success',), allow_early_resets=allow_early_resets)
    env.seed(seed)
    return env


def arg_parser():
    """
    Create an empty argparse.ArgumentParser.

    :return: (ArgumentParser)
    """
    import argparse
    return argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)


def atari_arg_parser():
    """
    Create an argparse.ArgumentParser for run_atari.py.

    :return: (ArgumentParser) parser {'--env': 'BreakoutNoFrameskip-v4', '--seed': 0, '--num-timesteps': int(1e7)}
    """
    parser = arg_parser()
    parser.add_argument('--env', help='environment ID', default='BreakoutNoFrameskip-v4')
    parser.add_argument('--seed', help='RNG seed', type=int, default=0)
    parser.add_argument('--num-timesteps', type=int, default=int(1e7))
    return parser


def mujoco_arg_parser():
    """
    Create an argparse.ArgumentParser for run_mujoco.py.

    :return:  (ArgumentParser) parser {'--env': 'Reacher-v2', '--seed': 0, '--num-timesteps': int(1e6), '--play': False}
    """
    parser = arg_parser()
    parser.add_argument('--env', help='environment ID', type=str, default='Reacher-v2')
    parser.add_argument('--seed', help='RNG seed', type=int, default=0)
    parser.add_argument('--num-timesteps', type=int, default=int(1e6))
    parser.add_argument('--play', default=False, action='store_true')
    return parser


def robotics_arg_parser():
    """
    Create an argparse.ArgumentParser for run_mujoco.py.

    :return: (ArgumentParser) parser {'--env': 'FetchReach-v0', '--seed': 0, '--num-timesteps': int(1e6)}
    """
    parser = arg_parser()
    parser.add_argument('--env', help='environment ID', type=str, default='FetchReach-v0')
    parser.add_argument('--seed', help='RNG seed', type=int, default=0)
    parser.add_argument('--num-timesteps', type=int, default=int(1e6))
    return parser
