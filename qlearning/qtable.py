from collections import deque
from numpy import max, abs, exp
from numpy.random import rand, randint, multinomial
import pandas as pd
import matplotlib.pyplot as plt


class SimpleMaze:
    def __init__(self):
        self.actions = ['left', 'right', 'up', 'down']
        self.DIMS = (4, 5)
        self.GOAL_STATE = (2, 2)
        self.GOAL_REWARD = 100
        self.WALL_REWARD = 0
        self.NULL_REWARD = 0
        self.state = None
        self.reset()

    def observe(self):
        return self.state

    def interact(self, action):
        next_state, reward = self.transition_(self.state, action)
        self.state = next_state
        return next_state, reward

    def transition_(self, current_state, action):
        if action == 'up':
            next_state, reward = (current_state, self.WALL_REWARD) if current_state[0] == 0 \
                else ((current_state[0]-1, current_state[1]), self.NULL_REWARD)
        elif action == 'down':
            next_state, reward = (current_state, self.WALL_REWARD) if current_state[0] == (self.DIMS[0] - 1) \
                else ((current_state[0]+1, current_state[1]), self.NULL_REWARD)
        elif action == 'left':
            next_state, reward = (current_state, self.WALL_REWARD) if current_state[1] == 0 \
                else ((current_state[0], current_state[1]-1), self.NULL_REWARD)
        elif action == 'right':
            next_state, reward = (current_state, self.WALL_REWARD) if current_state[1] == (self.DIMS[1] - 1) \
                else ((current_state[0], current_state[1]+1), self.NULL_REWARD)
        else:
            print 'I don\'t understand this action ({}), I\'ll stay.'.format(action)
            next_state, reward = current_state, self.NULL_REWARD
        reward = self.GOAL_REWARD if next_state == self.GOAL_STATE else reward
        return next_state, reward

    def reset(self):
        next_state = self.GOAL_STATE
        while next_state == self.GOAL_STATE:
            next_state = (randint(0, self.DIMS[0]), randint(0, self.DIMS[1]))
        self.state = next_state

    def isfinished(self):
        return self.state == self.GOAL_STATE


class QAgent(object):
    def __init__(self, actions=None, alpha=1.0, gamma=0.5, epsilon=0.0, explore_strategy='epsilon', **kwargs):
        super(QAgent, self).__init__(**kwargs)
        # static attributes
        if not actions:
            raise ValueError("Passed in None action list.")
        self.ACTIONS = actions
        self.ALPHA = alpha  # learning rate
        self.GAMMA = gamma  # discount factor
        self.EPSILON = epsilon  # exploration probability
        self.DEFAULT_QVAL = 0  # default initial value for Q table entries
        self.EXPLORE = explore_strategy
        # dynamic attributes
        self.last_state = None
        self.last_action = None
        self.q_table = {}

    def observe_and_act(self, observation, reward=None):
        try:
            state = self.transition_(observation=observation, reward=reward)
        except AttributeError:
            state = observation
        update_result = self.reinforce_(state=state, reward=reward)
        action = self.act_(state=state)
        self.last_state = state
        self.last_action = action
        return action, update_result

    def reset(self, foget_table=False):
        self.last_state = None
        self.last_action = None
        if foget_table:
            self.q_table = {}

    def reinforce_(self, state, reward):
        """ Improve agent based on current experience (last_state, last_action, reward, state)

        """
        last_state = self.last_state
        last_action = self.last_action
        if last_state is None or state is None:
            update_result = None
        else:
            update_result = self.update_table_(last_state, last_action, reward, state)
        return update_result

    def update_table_(self, last_state, last_action, reward, current_state):
        best_qval = max(self.lookup_table_(current_state))
        delta_q = reward + self.GAMMA * best_qval
        self.q_table[(last_state, last_action)] = \
            self.ALPHA * delta_q + (1 - self.ALPHA) * self.q_table[(last_state, last_action)] \
                if (last_state, last_action) in self.q_table else self.DEFAULT_QVAL
        return None

    def act_(self, state):
        """Agent choose an action based on current state.

        Parameters
        ----------
        state

        Returns
        -------

        """
        if not state:
            idx_action = randint(0, len(self.ACTIONS))  # if state cannot be internalized as state, random act
        elif self.EXPLORE == 'epsilon':
            if rand() < self.EPSILON:  # random exploration with "epsilon" prob.
                idx_action = randint(0, len(self.ACTIONS))
            else:  # select the best action with "1-epsilon" prob., break tie randomly
                q_vals = self.lookup_table_(state)
                max_qval = max(q_vals)
                idx_best_actions = [i for i in range(len(q_vals)) if q_vals[i] == max_qval]
                idx_action = idx_best_actions[randint(0, len(idx_best_actions))]
        elif self.EXPLORE == 'soft_probability':
                q_vals = self.lookup_table_(state)  # state = internal_state
                exp_q_vals = exp(q_vals)
                idx_action = multinomial(1, exp_q_vals/sum(exp_q_vals)).nonzero()[0][0]
        else:
            raise ValueError('Unknown keyword for exploration strategy!')
        return self.ACTIONS[idx_action]

    def lookup_table_(self, state):
        """ return the q values of all actions at a given state
        """
        return [self.q_table[(state, a)] if (state, a) in self.q_table else self.DEFAULT_QVAL for a in self.ACTIONS]


if __name__ == "__main__":
    maze = SimpleMaze()
    agent = QAgent(actions=maze.actions, alpha=0.5, gamma=0.5, explore_strategy='epsilon', epsilon=0.1)
    # logging
    path = deque()  # path in this episode
    episode_reward_rates = []
    num_episodes = 0
    cum_reward = 0
    cum_steps = 0

    # repeatedly run episodes
    while True:
        # initialization
        maze.reset()
        agent.reset(foget_table=False)
        action, _ = agent.observe_and_act(observation=None, reward=None)  # get and random action
        path.clear()
        episode_reward = 0
        episode_steps = 0
        # interact and reinforce repeatedly
        while not maze.isfinished():
            new_observation, reward = maze.interact(action)
            action, _ = agent.observe_and_act(observation=new_observation, reward=reward)
            path.append(new_observation)
            episode_reward += reward
            episode_steps += 1

        cum_steps += episode_steps
        cum_reward += episode_reward
        num_episodes += 1
        episode_reward_rates.append(episode_reward / episode_steps)
        if num_episodes % 100 == 0:
            print num_episodes, len(agent.q_table), cum_reward, cum_steps, 1.0 * cum_reward / cum_steps#, path
            cum_reward = 0
            cum_steps = 0
    win = 50
    # s = pd.rolling_mean(pd.Series([0]*win+episode_reward_rates), window=win, min_periods=1)
    # s.plot()
    # plt.show()
