import gym
import tensorflow as tf
from tensorflow import keras
import random
import numpy as np
import datetime as dt
import imageio
import os

# 
# conda activate tf
# export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CONDA_PREFIX/lib/
# conda install -c conda-forge cudatoolkit=11.2 cudnn=8.1.0
# o pip install tensorflow 
# pip install tensorflow-gpu
# o pip install gym
# o pip install gym[atari]
# o pip install autorom[accept-rom-license]
# pip install keras
# pip install keras-rl2
# o pip install imageio

# https://adventuresinmachinelearning.com/atari-space-invaders-dueling-q/
#
# uses PERSI to make training more efficient (take this out?)

# Fix for weird thing
# https://stackoverflow.com/questions/68614547/tensorflow-libdevice-not-found-why-is-it-not-found-in-the-searched-path
# export XLA_FLAGS=--xla_gpu_cuda_data_dir=/home/kali/.local/lib/python3.8/site-packages/jaxlib/cuda

#Use xming X server for windows
#run using 
#echo "export DISPLAY=localhost:0.0" >> ~/.bashrc
#. ~/.bashrc
# export DISPLAY=[IP]:0.0

STORE_PATH = "tensorboard"  # Path to where tensorboard logs are stored
MAX_EPSILON = 1  # Maximum probability of choosing a random action in epsilon-greedy algorithm
MIN_EPSILON = 0.1  # Minimum probability of choosing a random action in epsilon-greedy algorithm
EPSILON_MIN_ITER = 500000  # Number of iterations after which epsilon will have decreased from MAX_EPSILON to MIN_EPSILON
GAMMA = 0.99  # Discount factor in reinforcement learning
BATCH_SIZE = 32  # Number of samples used in each iteration of training
TAU = 0.08  # Hyperparameter for soft updating of the target network
POST_PROCESS_IMAGE_SIZE = (105, 80, 1)  # Size of processed images used as input to the neural network
DELAY_TRAINING = 50000  # Number of time steps to wait before starting training
BETA_DECAY_ITERS = 500000  # Number of iterations after which beta will have decayed from MAX_BETA to MIN_BETA
MIN_BETA = 0.4  # Minimum value of beta parameter
MAX_BETA = 1.0  # Maximum value of beta parameter
NUM_FRAMES = 4  # Number of frames stacked together as input to the neural network
GIF_RECORDING_FREQ = 100  # Frequency with which GIFs are recorded during training
MODEL_SAVE_FREQ = 100  # Frequency with which the trained model is saved

# Create an environment for the Space Invaders game, using the RGB array render mode
env = gym.make("SpaceInvaders-v0", render_mode="rgb_array")

# Get the number of possible actions in the game
num_actions = env.action_space.n

class DQModel(keras.Model):
    def __init__(self, hidden_size: int, num_actions: int, dueling: bool):
        # Initialize the model using the parent's constructor
        super(DQModel, self).__init__()
        # Save whether the model uses the dueling architecture
        self.dueling = dueling
        # Create the first convolutional layer with 16 filters, each of size 8x8, using a stride of 4
        self.conv1 = keras.layers.Conv2D(16, (8, 8), (4, 4), activation='relu')
        # Create the second convolutional layer with 32 filters, each of size 4x4, using a stride of 2
        self.conv2 = keras.layers.Conv2D(32, (4, 4), (2, 2), activation='relu')
        # Create a flatten layer to flatten the output of the second convolutional layer
        self.flatten = keras.layers.Flatten()
        # Create a dense layer with the specified hidden size, using the He normal kernel initializer
        self.adv_dense = keras.layers.Dense(hidden_size, activation='relu',
                                         kernel_initializer=keras.initializers.he_normal())
        # Create a dense layer with the specified number of actions, using the He normal kernel initializer
        self.adv_out = keras.layers.Dense(num_actions,
                                          kernel_initializer=keras.initializers.he_normal())
        # If the model uses the dueling architecture
        if dueling:
            # Create a dense layer with the specified hidden size, using the He normal kernel initializer
            self.v_dense = keras.layers.Dense(hidden_size, activation='relu',
                                         kernel_initializer=keras.initializers.he_normal())
            # Create a dense layer with a single output, using the He normal kernel initializer
            self.v_out = keras.layers.Dense(1, kernel_initializer=keras.initializers.he_normal())
            # Create a lambda layer to subtract the mean from the outputs of the advantage layer
            self.lambda_layer = keras.layers.Lambda(lambda x: x - tf.reduce_mean(x))
            # Create an Add layer to combine the value and advantage outputs
            self.combine = keras.layers.Add()

    # Define the forward pass of the model
    def call(self, input):
        # Pass the input through the first convolutional layer and apply ReLU activation
        x = self.conv1(input)
        # Pass the output of the first convolutional layer through the second convolutional layer and apply ReLU activation
        x = self.conv2(x)
        # Flatten the output of the second convolutional layer
        x = self.flatten(x)
        # Pass the output of the flatten layer through the advantage dense layer and apply ReLU activation
        adv = self.adv_dense(x)
        # Pass the output of the advantage dense layer through the advantage output layer
        adv = self.adv_out(adv)
        # If the model uses the dueling architecture
        if self.dueling:
            # Pass the output of the flatten layer through the value dense layer and apply ReLU activation
            v = self.v_dense(x)
            # Pass the output of the value dense layer through the value output layer
            v = self.v_out(v)
            # Pass the output of the advantage output layer through the lambda layer to subtract the mean
            norm_adv = self.lambda_layer(adv)
            # Pass the value and advantage outputs through the Add layer to combine them
            combined = self.combine([v, norm_adv])
            # Return the combined output
            return combined
        # If the model doesn't use the dueling architecture, return the advantage output
        return adv



def huber_loss(loss):
    return 0.5 * loss ** 2 if abs(loss) < 1.0 else abs(loss) - 0.5
# The Huber loss function is a loss function that is more robust 
# than the mean squared error loss function. It is defined as the 
# mean squared error loss function for small values of the error, 
# but becomes a mean absolute error loss function for larger values of the error. 
# This makes it more resilient to the effects of outliers, since the loss for these points 
# is not squared and therefore not disproportionately large compared to the rest of the data.
# Was experimenting with this, but tf.keras.losses.Huber() is more efficient.


primary_network = DQModel(256, num_actions, True)
target_network = DQModel(256, num_actions, True)
# each model has 256 hidden units.

primary_network.compile(optimizer=keras.optimizers.Adam(), loss=tf.keras.losses.Huber())
# make target_network = primary_network
for t, e in zip(target_network.trainable_variables, primary_network.trainable_variables):
    t.assign(e)

class Node: 
    def __init__(self, left, right, is_leaf: bool = False, idx = None):
        self.left = left
        self.right = right
        self.is_leaf = is_leaf
        self.value = sum(n.value for n in (left, right) if n is not None)
        self.parent = None
        self.idx = idx  # this value is only set for leaf nodes
        if left is not None:
            left.parent = self
        if right is not None:
            right.parent = self

    @classmethod
    def create_leaf(cls, value, idx):
        leaf = cls(None, None, is_leaf=True, idx=idx)
        leaf.value = value
        return leaf

# This code defines a basic class for a Node in a tree data structure. 
# The Node class has several attributes, including left and right for 
# the left and right child nodes, is_leaf for whether the node is a leaf node, 
# value for the value of the node, parent for the parent node, and idx for the index of the node. 
# The __init__ method is used to initialize a new Node object, and takes several arguments 
# including left, right, is_leaf, and idx. The value attribute is set to the sum of
# the values of the left and right child nodes, and the parent attributes of the left and 
# right child nodes are set to the new Node object. The create_leaf class method can be used 
# to create a new leaf Node with a given value and index.


def create_tree(input: list):
    nodes = [Node.create_leaf(v, i) for i, v in enumerate(input)]
    leaf_nodes = nodes
    while len(nodes) > 1:
        inodes = iter(nodes)
        nodes = [Node(*pair) for pair in zip(inodes, inodes)]
    
    return nodes[0], leaf_nodes

# This code defines a method to create a tree of nodes

def retrieve(value: float, node: Node):
    if node.is_leaf:
        return node
    
    if node.left.value >= value: 
        return retrieve(value, node.left)
    else:
        return retrieve(value - node.left.value, node.right)

# This code defines a method to create a tree of nodes

def update(node: Node, new_value: float):
    change = new_value - node.value

    node.value = new_value
    propagate_changes(change, node.parent)


def propagate_changes(change: float, node: Node):
    node.value += change

    if node.parent is not None:
        propagate_changes(change, node.parent)


class Memory(object):
    def __init__(self, size: int):
        self.size = size
        self.curr_write_idx = 0
        self.available_samples = 0
        self.buffer = [(np.zeros((POST_PROCESS_IMAGE_SIZE[0], POST_PROCESS_IMAGE_SIZE[1]), dtype=np.float32), 0.0, 0.0, 0.0) for i in range(self.size)]
        self.base_node, self.leaf_nodes = create_tree([0 for i in range(self.size)])
        self.frame_idx = 0
        self.action_idx = 1
        self.reward_idx = 2
        self.terminal_idx = 3
        self.beta = 0.4
        self.alpha = 0.6
        self.min_priority = 0.01

    def append(self, experience: tuple, priority: float):
        self.buffer[self.curr_write_idx] = experience
        self.update(self.curr_write_idx, priority)
        self.curr_write_idx += 1
        # reset the current writer position index if creater than the allowed size
        if self.curr_write_idx >= self.size:
            self.curr_write_idx = 0
        # max out available samples at the memory buffer size
        if self.available_samples + 1 < self.size:
            self.available_samples += 1
        else:
            self.available_samples = self.size - 1

    def update(self, idx: int, priority: float):
        update(self.leaf_nodes[idx], self.adjust_priority(priority))

    def adjust_priority(self, priority: float):
        return np.power(priority + self.min_priority, self.alpha)

    def sample(self, num_samples: int):
        sampled_idxs = []
        is_weights = []
        sample_no = 0
        while sample_no < num_samples:
            sample_val = np.random.uniform(0, self.base_node.value)
            samp_node = retrieve(sample_val, self.base_node)
            if NUM_FRAMES - 1 < samp_node.idx < self.available_samples - 1:
                sampled_idxs.append(samp_node.idx)
                p = samp_node.value / self.base_node.value
                is_weights.append((self.available_samples + 1) * p)
                sample_no += 1
        # apply the beta factor and normalise so that the maximum is_weight < 1
        is_weights = np.array(is_weights)
        is_weights = np.power(is_weights, -self.beta)
        is_weights = is_weights / np.max(is_weights)
        # now load up the state and next state variables according to sampled idxs
        states = np.zeros((num_samples, POST_PROCESS_IMAGE_SIZE[0], POST_PROCESS_IMAGE_SIZE[1], NUM_FRAMES),
                             dtype=np.float32)
        next_states = np.zeros((num_samples, POST_PROCESS_IMAGE_SIZE[0], POST_PROCESS_IMAGE_SIZE[1], NUM_FRAMES),
                            dtype=np.float32)
        actions, rewards, terminal = [], [], [] 
        for i, idx in enumerate(sampled_idxs):
            for j in range(NUM_FRAMES):
                states[i, :, :, j] = self.buffer[idx + j - NUM_FRAMES + 1][self.frame_idx][:, :, 0]
                next_states[i, :, :, j] = self.buffer[idx + j - NUM_FRAMES + 2][self.frame_idx][:, :, 0]
            actions.append(self.buffer[idx][self.action_idx])
            rewards.append(self.buffer[idx][self.reward_idx])
            terminal.append(self.buffer[idx][self.terminal_idx])
        return states, np.array(actions), np.array(rewards), next_states, np.array(terminal), sampled_idxs, is_weights

# The Memory class is used to store past experiences from the environment in a replay buffer, 
# which is then used to train the reinforcement learning model. The Memory class uses a priority
# queue implemented as a sum tree data structure to prioritize experiences in the replay buffer 
# according to their importance, with more important experiences being more likely to be sampled for training.

memory = Memory(200000)

# preprocesses an image to be inputted into the network
def image_preprocess(image, new_size=(105, 80)):
    # convert to greyscale, resize and normalize the image
    # image = image[0]
    #print(image)
    image = tf.image.rgb_to_grayscale(image)
    image = tf.image.resize(image, new_size)
    image = image / 255
    return image

# chooses an action (epsilon greedy function)
def choose_action(state, primary_network, eps, step):
    if step < DELAY_TRAINING:
        return random.randint(0, num_actions - 1)
    else:
        if random.random() < eps:
            return random.randint(0, num_actions - 1)
        else:
            return np.argmax(primary_network(tf.reshape(state, (1, POST_PROCESS_IMAGE_SIZE[0],
                                                           POST_PROCESS_IMAGE_SIZE[1], NUM_FRAMES)).numpy()))

# Updates from primary network
def update_network(primary_network, target_network):
    for t, e in zip(target_network.trainable_variables, primary_network.trainable_variables):
        t.assign(t * (1 - TAU) + e * TAU)

# Processes the state stack.
def process_state_stack(state_stack, state):
    for i in range(1, state_stack.shape[-1]):
        state_stack[:, :, i - 1].assign(state_stack[:, :, i])
    state_stack[:, :, -1].assign(state[:, :, 0])
    return state_stack


# Records a gif replay of the entire game using imageio.
def record_gif(frame_list, episode, fps=50):
    if(len(frame_list) > 50):
        imageio.mimsave(STORE_PATH + "\\SPACE_INVADERS_EPISODE-eps{}-r{}.gif".format(episode, reward), frame_list, fps=fps) #duration=duration_per_frame)ation_per_frame)


def get_per_error(states, actions, rewards, next_states, terminal, primary_network, target_network):
    # predict Q(s,a) given the batch of states
    prim_qt = primary_network(states)
    # predict Q(s',a') from the evaluation network
    prim_qtp1 = primary_network(next_states)
    # copy the prim_qt tensor into the target_q tensor - we then will update one index corresponding to the max action
    target_q = prim_qt.numpy()
    # the action selection from the primary / online network
    prim_action_tp1 = np.argmax(prim_qtp1.numpy(), axis=1)
    # the q value for the prim_action_tp1 from the target network
    q_from_target = target_network(next_states)
    updates = rewards + (1 - terminal) * GAMMA * q_from_target.numpy()[:, prim_action_tp1]
    target_q[:, actions] = updates
    # calculate the loss / error to update priorites
    error = [huber_loss(target_q[i, actions[i]] - prim_qt.numpy()[i, actions[i]]) for i in range(states.shape[0])]
    return target_q, error


def train(primary_network, memory, target_network):
    states, actions, rewards, next_states, terminal, idxs, is_weights = memory.sample(BATCH_SIZE)
    target_q, error = get_per_error(states, actions, rewards, next_states, terminal, primary_network, target_network)
    for i in range(len(idxs)):
        memory.update(idxs[i], error[i])
    loss = primary_network.train_on_batch(states, target_q, is_weights)
    return loss

num_episodes = 1501
# In practice, model weights are saved as multiples of 100. Therefore, set num_episodes to be a multiple of 100 + 1 (0 counts as an episode)
eps = MAX_EPSILON
render = False # If true, will show bot working in real time. Set false to save on graphics power.
train_writer = tf.summary.create_file_writer(STORE_PATH + "/DuelingQPERSI_{}".format(dt.datetime.now().strftime('%d%m%Y%H%M')))
steps = 0
for i in range(num_episodes):
    state = env.reset()
    state = image_preprocess(state[0])
    state_stack = tf.Variable(np.repeat(state.numpy(), NUM_FRAMES).reshape((POST_PROCESS_IMAGE_SIZE[0],
                                                                            POST_PROCESS_IMAGE_SIZE[1],
                                                                            NUM_FRAMES)))
    cnt = 1
    avg_loss = 0
    tot_reward = 0
    if i % GIF_RECORDING_FREQ == 0:
        frame_list = []
    while True:
        if render:
            env.render()
        action = choose_action(state_stack, primary_network, eps, steps)
        next_state, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        tot_reward += reward
        if i % GIF_RECORDING_FREQ == 0:
            frame_list.append(tf.cast(tf.image.resize(next_state, (480, 320)), tf.uint8).numpy())
        next_state = image_preprocess(next_state)
        old_state_stack = state_stack
        state_stack = process_state_stack(state_stack, next_state)

        if steps > DELAY_TRAINING:
            loss = train(primary_network, memory, target_network)
            update_network(primary_network, target_network)
            _, error = get_per_error(tf.reshape(old_state_stack, (1, POST_PROCESS_IMAGE_SIZE[0], POST_PROCESS_IMAGE_SIZE[1], NUM_FRAMES)), np.array([action]), np.array([reward]), tf.reshape(state_stack, (1, POST_PROCESS_IMAGE_SIZE[0], POST_PROCESS_IMAGE_SIZE[1], NUM_FRAMES)), np.array([done]), primary_network, target_network)
            # store in memory
            memory.append((next_state, action, reward, done), error[0])
        else:
            loss = -1
            # store in memory - default the priority to the reward
            memory.append((next_state, action, reward, done), reward)
        avg_loss += loss

        # linearly decay the eps and PER beta values
        if steps > DELAY_TRAINING:
            eps = MAX_EPSILON - ((steps - DELAY_TRAINING) / EPSILON_MIN_ITER) * \
                  (MAX_EPSILON - MIN_EPSILON) if steps < EPSILON_MIN_ITER else \
                MIN_EPSILON
            beta = MIN_BETA + ((steps - DELAY_TRAINING) / BETA_DECAY_ITERS) * \
                  (MAX_BETA - MIN_BETA) if steps < BETA_DECAY_ITERS else \
                MAX_BETA
            memory.beta = beta
        steps += 1

        if done:
            if steps > DELAY_TRAINING:
                avg_loss /= cnt
                print("Episode: {}, Reward: {}, avg loss: {:.5f}, eps: {:.3f}".format(i, tot_reward, avg_loss, eps))
                with train_writer.as_default():
                    tf.summary.scalar('reward', tot_reward, step=i)
                    tf.summary.scalar('avg loss', avg_loss, step=i)
            else:
                print("Pre-training...Episode: {}".format(i))
            if i % GIF_RECORDING_FREQ == 0:
                record_gif(frame_list, i, tot_reward)
            break

        cnt += 1
    if i % MODEL_SAVE_FREQ == 0: # and i != 0:
        primary_network.save_weights(STORE_PATH + "/checkpoints/cp_primary_network_episode_{}.ckpt".format(i))
        target_network.save_weights(STORE_PATH + "/checkpoints/cp_target_network_episode_{}.ckpt".format(i))

#primary_network
#target_network

#primary_network = DQModel(256, num_actions, True)
#target_network = DQModel(256, num_actions, True)
# primary_network.load_weights(STORE_PATH + "/checkpoints/cp_primary_network_episode_1000.ckpt")
# target_network.load_weights(STORE_PATH + "/checkpoints/cp_target_network_episode_1000.ckpt")

# env = gym.make("SpaceInvaders-v0", render_mode="human")
# render = True

# for i in range(1):
#     state = env.reset()
#     state = image_preprocess(state[0])
#     state_stack = tf.Variable(np.repeat(state.numpy(), NUM_FRAMES).reshape((POST_PROCESS_IMAGE_SIZE[0],
#                                                                             POST_PROCESS_IMAGE_SIZE[1],
#                                                                             NUM_FRAMES)))
#     cnt = 1
#     avg_loss = 0
#     tot_reward = 0
#     if i % GIF_RECORDING_FREQ == 0:
#         frame_list = []
#     while True:
#         if render:
#             env.render()
#         action = choose_action(state_stack, primary_network, 0, 51000) # guarantees primary network is chosen
#         next_state, reward, terminated, truncated, info = env.step(action)
#         done = terminated or truncated
#         tot_reward += reward
#         #if i % GIF_RECORDING_FREQ == 0:
#         #    frame_list.append(tf.cast(tf.image.resize(next_state, (480, 320)), tf.uint8).numpy())
#         next_state = image_preprocess(next_state)
#         old_state_stack = state_stack
#         state_stack = process_state_stack(state_stack, next_state)