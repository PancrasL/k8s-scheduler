#!/bin/python
# coding:utf-8

from tensorflow.examples.tutorials.mnist import input_data
import tensorflow as tf
import datetime
import time
import socket
import os

tf.app.flags.DEFINE_string("ps_hosts", "", "Comma-separated list of hostname:port pairs")
tf.app.flags.DEFINE_string("worker_hosts", "", "Comma-separated list of hostname:port pairs")
tf.app.flags.DEFINE_string("job_name", "", "One of 'ps', 'worker'")
tf.app.flags.DEFINE_integer("task_index", 0, "Index of task within the job")

FLAGS = tf.app.flags.FLAGS

is_chief = (FLAGS.task_index == 0)

# Parameters
learning_rate = 0.001
regularization_rate = 0.01
training_epochs = 20
batch_size = 128
display_step = 100

# total_steps = 100000
# 方便测试
total_steps = {TOTAL_STEPS}

# Network Parameters
n_inputs = 28   # MNIST data input (img shape: 28*28)
n_steps = 28    # time steps
n_hidden_units = 128   # neurons in hidden layer
n_classes = 10      # MNIST classes (0-9 digits)

# checkpoint 目录
logs_train_dir = "./checkpoint/"

# set random seed for comparing the two result calculations
tf.set_random_seed(1)


def rnn(X, weights, biases):
    # hidden layer for input to cell
    ########################################

    # transpose the inputs shape from
    # X ==> (128 batch * 28 steps, 28 inputs)
    X = tf.reshape(X, [-1, n_inputs])

    # into hidden
    # X_in = (128 batch * 28 steps, 128 hidden)
    X_in = tf.matmul(X, weights['in']) + biases['in']
    # X_in ==> (128 batch, 28 steps, 128 hidden)
    X_in = tf.reshape(X_in, [-1, n_steps, n_hidden_units])

    # cell
    ##########################################

    # basic LSTM Cell.
    lstm_cell = tf.nn.rnn_cell.BasicLSTMCell(n_hidden_units, forget_bias=1.0, state_is_tuple=True)
    # lstm cell is divided into two parts (c_state, h_state)
    init_state = lstm_cell.zero_state(batch_size, dtype=tf.float32)

    # You have 2 options for following step.
    # 1: tf.nn.rnn(cell, inputs);
    # 2: tf.nn.dynamic_rnn(cell, inputs).
    # If use option 1, you have to modified the shape of X_in, go and check out this:
    # https://github.com/aymericdamien/TensorFlow-Examples/blob/master/examples/3_NeuralNetworks/recurrent_network.py
    # In here, we go for option 2.
    # dynamic_rnn receive Tensor (batch, steps, inputs) or (steps, batch, inputs) as X_in.
    # Make sure the time_major is changed accordingly.
    outputs, final_state = tf.nn.dynamic_rnn(lstm_cell, X_in, initial_state=init_state, time_major=False)

    # hidden layer for output as the final results
    #############################################
    # results = tf.matmul(final_state[1], weights['out']) + biases['out']

    # # or
    # unpack to list [(batch, outputs)..] * steps
    outputs = tf.unpack(tf.transpose(outputs, [1, 0, 2]))    # states is the last outputs
    results = tf.matmul(outputs[-1], weights['out']) + biases['out']

    return results


def main(_):
    ps_hosts = FLAGS.ps_hosts.split(",")
    worker_hosts = FLAGS.worker_hosts.split(",")

    # Create a cluster from the parameter server and worker hosts.
    cluster = tf.train.ClusterSpec({"ps": ps_hosts, "worker": worker_hosts})

    # Create and start a server for the local task.
    server = tf.train.Server(cluster,
                             job_name=FLAGS.job_name,
                             task_index=FLAGS.task_index)
    print("Cluster job: %s, task_index: %d, target: %s" % (FLAGS.job_name, FLAGS.task_index, server.target))
    if FLAGS.job_name == "ps":
        server.join()
    elif FLAGS.job_name == "worker":

        mnist = None
        while not mnist:
            # Get data ...
            try:
                mnist = input_data.read_data_sets("data", one_hot=True)

                file_name = "/mnt/" + "mnist_data.txt"
                f1 = open(file_name, 'w')
                f1.write(mnist)
                f1.close()

                break

            except:
                time.sleep(3)

        # Get data ...
        # mnist = input_data.read_data_sets("data", one_hot=True)

        # Assigns ops to the local worker by default.
        with tf.device(tf.train.replica_device_setter(
                worker_device="/job:worker/task:%d" % FLAGS.task_index,
                cluster=cluster)):

            # tf Graph input
            x = tf.placeholder(tf.float32, [None, n_steps, n_inputs])
            y = tf.placeholder(tf.float32, [None, n_classes])

            # Define weights
            weights = {
                # (28, 128)
                'in': tf.Variable(tf.random_normal([n_inputs, n_hidden_units])),
                # (128, 10)
                'out': tf.Variable(tf.random_normal([n_hidden_units, n_classes]))
            }
            biases = {
                # (128, )
                'in': tf.Variable(tf.constant(0.1, shape=[n_hidden_units, ])),
                # (10, )
                'out': tf.Variable(tf.constant(0.1, shape=[n_classes, ]))
            }

            global_step = tf.Variable(0)

            # Define operations
            pred = rnn(x, weights, biases)

            # the error between prediction and real data
            cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(pred, y))
            train_op = tf.train.AdamOptimizer(learning_rate).minimize(cost, global_step=global_step)

            # Test trained model
            correct_prediction = tf.equal(tf.argmax(pred, 1), tf.argmax(y, 1))
            accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
  
            saver = tf.train.Saver()
            summary_op = tf.merge_all_summaries()
            init_op = tf.initialize_all_variables()

        # Create a "Supervisor", which oversees the training process.
        sv = tf.train.Supervisor(is_chief=(FLAGS.task_index == 0),
                                 #logdir="/Users/urey/PycharmProjects/tensorflow_demo/notes/tensorflow/checkpoint/",
                                 logdir="./checkpoint/",
                                 init_op=init_op,
                                 summary_op=summary_op,
                                 saver=saver,
                                 global_step=global_step,
                                 save_model_secs=600)

        if is_chief:
            print("Worker %d: Initializing session..." % FLAGS.task_index)
        else:
            print("Worker %d: Waiting for session to be initialized..." % FLAGS.task_index)

        # The supervisor takes care of session initialization and restoring from
        # a checkpoint.
        sess = sv.prepare_or_wait_for_session(server.target)

        # Start queue runners for the input pipelines (if ang).
        sv.start_queue_runners(sess)

        # Loop until the supervisor shuts down (or total_steps steps have completed).
        starttime = datetime.datetime.now()
        f1 = open(file_name,'w')
        f1.write(str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        f1.write("\n")
        f1.close()

        step = 0
        while not sv.should_stop() and step < total_steps:
            batch_xs, batch_ys = mnist.train.next_batch(batch_size)
            batch_xs = batch_xs.reshape([batch_size, n_steps, n_inputs])

            _, loss_v, step = sess.run([train_op, cost, global_step], feed_dict={x: batch_xs, y: batch_ys})
            if step % display_step == 0:
                # 保存模型
                checkpoint_path = os.path.join(logs_train_dir, './model.ckpt')
                saver.save(sess, checkpoint_path, global_step=step)

                print time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                print("Step %d in task %d, loss %f" % (step, FLAGS.task_index, loss_v))
        print("done.")

        endtime = datetime.datetime.now()
        print (endtime - starttime).seconds

        file_name = "/mnt/" + socket.gethostname() + "_" + str(
            FLAGS.job_name) + "_" + str(FLAGS.task_index) + "_time.txt"
        #file_name = str(FLAGS.job_name) + "_" + str(task_index) + "_time.txt"
        f1 = open(file_name,'a')
        f1.write(str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        f1.write("\n")
        f1.write(str((endtime - starttime).seconds))
        f1.write("\n")
        f1.close()

        file_name = "/mnt/" + "finish-" + socket.gethostname() + "_" + str(FLAGS.job_name) + "_" + str(FLAGS.task_index) + "_time.txt"
        f1 = open(file_name, 'w')
        f1.write("useless file... just for a flag that shows the worker finished task...")
        f1.close()

        #file_name = str(FLAGS.job_name) + "_" + str(task_index) + "_time.txt"
        #f1 = open(file_name,'w')
        #f1.write(str((endtime - starttime).seconds))
        #f1.write("\n")
        #f1.close()
        
        if FLAGS.task_index != 0:
            print("accuracy: %f" % sess.run(accuracy, feed_dict={x: mnist.test.images,
                                                             y: mnist.test.labels}))
if __name__ == "__main__":
    tf.app.run()

