'''
A DQN model to solve Acrobot problem.
Based on http://www.nervanasys.com/demystifying-deep-reinforcement-learning/
Implemented by Li Bin
'''

import gym
import tensorflow as tf
import random
import numpy as np
from argparse import ArgumentParser
import datetime
import copy
import random
import math
import numpy as np
import matplotlib.pyplot as plt
import time

OUT_DIR = 'acrobot-experiment' # default saving directory
MAX_SCORE_QUEUE_SIZE = 100  # number of episode scores to calculate average performance
GAME = 'Acrobot-v1'    # name of game
TIMESTEP_LIMIT = 1000   # Time step limit of each episode
global num_hops
num_hops = 0

def get_options():
    parser = ArgumentParser()
    parser.add_argument('--MAX_EPISODE', type=int, default=5000,
                        help='max number of episodes iteration')
    parser.add_argument('--ACTION_DIM', type=int, default=3,
                        help='number of actions one can take')
    parser.add_argument('--OBSERVATION_DIM', type=int, default=6,
                        help='number of observations one can see')
    parser.add_argument('--GAMMA', type=float, default=0.9,
                        help='discount factor of Q learning')
    parser.add_argument('--INIT_EPS', type=float, default=1.0,
                        help='initial probability for randomly sampling action')
    parser.add_argument('--FINAL_EPS', type=float, default=1e-5,
                        help='finial probability for randomly sampling action')
    parser.add_argument('--EPS_DECAY', type=float, default=0.8,
                        help='epsilon decay rate')
    parser.add_argument('--EPS_ANNEAL_STEPS', type=int, default=6000,
                        help='steps interval to decay epsilon')
    parser.add_argument('--LR', type=float, default=1e-4,
                        help='learning rate')
    parser.add_argument('--MAX_EXPERIENCE', type=int, default=60000,
                        help='size of experience replay memory')
    parser.add_argument('--BATCH_SIZE', type=int, default=512,
                        help='mini batch size'),
    parser.add_argument('--H1_SIZE', type=int, default=128,
                        help='size of hidden layer 1')
    parser.add_argument('--H2_SIZE', type=int, default=128,
                        help='size of hidden layer 2')
    parser.add_argument('--H3_SIZE', type=int, default=128,
                        help='size of hidden layer 3')
    options = parser.parse_args()
    return options

'''
The DQN model itself.
Remain unchanged when applied to different problems.
'''
class QAgent:
    
    # A naive neural network with 3 hidden layers and relu as non-linear function.
    def __init__(self, options):
        self.W1 = self.weight_variable([options.OBSERVATION_DIM, options.H1_SIZE])
        self.b1 = self.bias_variable([options.H1_SIZE])
        self.W2 = self.weight_variable([options.H1_SIZE, options.H2_SIZE])
        self.b2 = self.bias_variable([options.H2_SIZE])
        self.W3 = self.weight_variable([options.H2_SIZE, options.H3_SIZE])
        self.b3 = self.bias_variable([options.H3_SIZE])
        self.W4 = self.weight_variable([options.H3_SIZE, options.ACTION_DIM])
        self.b4 = self.bias_variable([options.ACTION_DIM])
    
    # Weights initializer
    def xavier_initializer(self, shape):
        dim_sum = np.sum(shape)
        if len(shape) == 1:
            dim_sum += 1
        bound = np.sqrt(6.0 / dim_sum)
        return tf.random_uniform(shape, minval=-bound, maxval=bound)

    # Tool function to create weight variables
    def weight_variable(self, shape):
        return tf.Variable(self.xavier_initializer(shape))

    # Tool function to create bias variables
    def bias_variable(self, shape):
        return tf.Variable(self.xavier_initializer(shape))

    # Add options to graph
    def add_value_net(self, options):
        observation = tf.placeholder(tf.float32, [None, options.OBSERVATION_DIM])
        h1 = tf.nn.relu(tf.matmul(observation, self.W1) + self.b1)
        h2 = tf.nn.relu(tf.matmul(h1, self.W2) + self.b2)
        h3 = tf.nn.relu(tf.matmul(h2, self.W3) + self.b3)
        Q = tf.squeeze(tf.matmul(h3, self.W4) + self.b4)
        return observation, Q

    # Sample action with random rate eps
    def sample_action(self, Q, feed, eps, options):
        if random.random() <= eps:
            action_index = env.action_space.sample()
        else:
            act_values = Q.eval(feed_dict=feed)
            action_index = np.argmax(act_values)
        action = np.zeros(options.ACTION_DIM)
        action[action_index] = 1
        return action

        # Sample action with random rate eps
    def sample_action_ret(self, Q, feed, eps, options, T, is_exploring, 
        act_queue, rwd_queue, next_obs_queue, exp_pointer, score):
        action = np.zeros(options.ACTION_DIM)
        q = -1
        if random.random() <= eps: # Decide to explore alternative path
            action_index = env.action_space.sample()
            action[action_index] = 1
            return action, q, None, True, True
        else: # "Normal" greedy learning
            act_values = Q.eval(feed_dict=feed)
            action_index = np.argmax(act_values)
            action[action_index] = 1
            q = np.max(act_values)
            action[action_index] = 1
            return action, q, T, is_exploring, False

def weighted_lasso_state(Q, feed, options, act_queue, rwd_queue, next_obs_queue, exp_pointer, score):
    global num_hops
    num_hops = num_hops+1
    lasso_env = gym.make(GAME)
    lasso_env.hop_to(env.get_state())

    visited_states = {}
    curr_state = tuple(env.get_state())
    feed_dict = feed

    lasso_act_queue = copy.deepcopy(act_queue)
    lasso_rwd_queue = copy.deepcopy(rwd_queue)
    lasso_next_obs_queue = copy.deepcopy(next_obs_queue)
    lasso_exp_pointer = copy.deepcopy(exp_pointer)
    lasso_score = np.empty([options.MAX_EXPERIENCE])
    lasso_score[exp_pointer]=score

    while(curr_state not in visited_states):
        visited_states[curr_state] = lasso_exp_pointer
        act_values = Q.eval(feed_dict)

        action_index = np.argmax(act_values)
        action = np.zeros(options.ACTION_DIM)
        action[action_index] = 1

        lasso_act_queue[lasso_exp_pointer] = action
        observation, reward, done, _ = lasso_env.step(np.argmax(action))
        curr_state = tuple(lasso_env.get_state())
        lasso_score[lasso_exp_pointer] += reward
        reward += lasso_score[lasso_exp_pointer] / 100 # Reward will be the accumulative score divied by 100
        lasso_score[lasso_exp_pointer] = score
        
        if done:
            reward = 1000 # If make it, send a big reward
            observation = np.zeros_like(observation)

        feed_dict = {feed.keys()[0] : np.reshape(observation, (1, -1))}

        lasso_rwd_queue[lasso_exp_pointer] = reward
        lasso_next_obs_queue[lasso_exp_pointer] = observation

        lasso_exp_pointer += 1
        if lasso_exp_pointer == options.MAX_EXPERIENCE:
            lasso_exp_pointer = 0 # Refill the replay memory if it is full
    hop_to = random.choice(visited_states.keys())
    return (hop_to, lasso_act_queue, lasso_rwd_queue, lasso_next_obs_queue, visited_states[hop_to],
        lasso_score[visited_states[hop_to]])

def train(env):
    all_scores = []
    all_times = []
    hopping = True
    if hopping:
        T = None
        is_exploring = False

    print datetime.datetime.now()
    # Define placeholders to catch inputs and add options
    options = get_options()
    agent = QAgent(options)
    sess = tf.InteractiveSession()
    
    obs, Q1 = agent.add_value_net(options)
    act = tf.placeholder(tf.float32, [None, options.ACTION_DIM])
    rwd = tf.placeholder(tf.float32, [None, ])
    next_obs, Q2 = agent.add_value_net(options)
    
    values1 = tf.reduce_sum(tf.mul(Q1, act), reduction_indices=1)
    values2 = rwd + options.GAMMA * tf.reduce_max(Q2, reduction_indices=1)
    loss = tf.reduce_mean(tf.square(values1 - values2))
    train_step = tf.train.AdamOptimizer(options.LR).minimize(loss)
    
    sess.run(tf.initialize_all_variables())
    
    # saving and loading networks
    saver = tf.train.Saver()
    checkpoint = tf.train.get_checkpoint_state("checkpoints-acrobot")
    if checkpoint and checkpoint.model_checkpoint_path:
        saver.restore(sess, checkpoint.model_checkpoint_path)
        print("Successfully loaded:", checkpoint.model_checkpoint_path)
    else:
        print("Could not find old network weights")
    
    # Some initial local variables
    feed = {}
    eps = options.INIT_EPS
    global_step = 0
    exp_pointer = 0
    learning_finished = False
    
    # The replay memory
    obs_queue = np.empty([options.MAX_EXPERIENCE, options.OBSERVATION_DIM])
    act_queue = np.empty([options.MAX_EXPERIENCE, options.ACTION_DIM])
    rwd_queue = np.empty([options.MAX_EXPERIENCE])
    next_obs_queue = np.empty([options.MAX_EXPERIENCE, options.OBSERVATION_DIM])
    start = time.time()
    # Score cache
    score_queue = []

    for i_episode in xrange(options.MAX_EPISODE):
        observation = env.reset()
        done = False
        score = 0
        sum_loss_value = 0
        epi_step = 0
        
        while not done:
            global_step += 1
            epi_step += 1
            if global_step % options.EPS_ANNEAL_STEPS == 0 and eps > options.FINAL_EPS:
                eps = eps * options.EPS_DECAY
            #env.render()
            
            obs_queue[exp_pointer] = observation
            if hopping:
                if (T > 0 and is_exploring): # Gamma pruning        
                    hop, act_queue, rwd_queue, next_obs_queue, exp_pointer, score = weighted_lasso_state(Q1, 
                        {obs : np.reshape(observation, (1, -1))}, options, act_queue, rwd_queue, next_obs_queue, exp_pointer, score)
                    env.hop_to(hop)
                    action = np.zeros(options.ACTION_DIM)
                    q = -1
                    T = None
                    is_exploring = False
                else:
                    action, q, T, is_exploring, start_exploring = agent.sample_action_ret(
                        Q1, {obs : np.reshape(observation, (1, -1))}, 
                        eps, 
                        options, 
                        T, 
                        is_exploring,
                        act_queue, 
                        rwd_queue, 
                        next_obs_queue, 
                        exp_pointer, 
                        score)
            else:
                action = agent.sample_action(Q1, {obs : np.reshape(observation, (1, -1))}, eps, options)
            
            act_queue[exp_pointer] = action
            observation, reward, done, _ = env.step(np.argmax(action))

            if hopping:
                if T is None:
                    T = reward + options.GAMMA*q # First hop
                elif(not T > 1e10):
                    T = (T-reward)/options.GAMMA # Recursive formula

            score += reward
            reward += score / 100 # Reward will be the accumulative score divied by 100

            if done and epi_step < TIMESTEP_LIMIT:
                reward = 1000 # If make it, send a big reward
                observation = np.zeros_like(observation)
            
            rwd_queue[exp_pointer] = reward
            next_obs_queue[exp_pointer] = observation
    
            exp_pointer += 1
            if exp_pointer == options.MAX_EXPERIENCE:
                exp_pointer = 0 # Refill the replay memory if it is full
    
            if global_step >= options.MAX_EXPERIENCE:
                rand_indexs = np.random.choice(options.MAX_EXPERIENCE, options.BATCH_SIZE)
                feed.update({obs : obs_queue[rand_indexs]})
                feed.update({act : act_queue[rand_indexs]})
                feed.update({rwd : rwd_queue[rand_indexs]})
                feed.update({next_obs : next_obs_queue[rand_indexs]})
                if not learning_finished:   # If not solved, we train and get the step loss
                    step_loss_value, _ = sess.run([loss, train_step], feed_dict = feed)
                else:   # If solved, we just get the step loss
                    step_loss_value = sess.run(loss, feed_dict = feed)
                # Use sum to calculate average loss of this episode
                sum_loss_value += step_loss_value
    
        print "====== Episode {} ended with score = {}, avg_loss = {}, eps = {} ======".format(i_episode+1, score, sum_loss_value / epi_step, eps)
        score_queue.append(score)
        all_scores.append(score)
        end = time.time()
        all_times.append(end-start)
        if len(score_queue) > MAX_SCORE_QUEUE_SIZE:
            score_queue.pop(0)
            if np.mean(score_queue) > -100:  # The threshold of being solved
                learning_finished = True
            else:
                learning_finished = False
        if learning_finished:
            print "Testing !!!"
            print datetime.datetime.now()
        if i_episode % 100 == 0:
            np.savetxt("test-results/Hopping_"+"results.csv", all_scores, delimiter=",")
            np.savetxt("test-results/Hopping_"+"timings.csv", all_times, delimiter=",")
            fig = plt.figure()
            plt.plot(np.arange(0,i_episode+1),np.asarray(all_scores))
            plt.xlabel('Episodes')
            plt.ylabel('Score')
            fig.savefig("test-results/Hopping_"+"plot.png")
        # save progress every 100 episodes
        if learning_finished and i_episode % 100 == 0:
            saver.save(sess, 'checkpoints-acrobot/' + GAME + '-dqn', global_step = global_step)



if __name__ == "__main__":
    env = gym.make(GAME)
    env.spec.timestep_limit = TIMESTEP_LIMIT
    env.monitor.start(OUT_DIR, force=True)
    train(env)
    env.monitor.close()
