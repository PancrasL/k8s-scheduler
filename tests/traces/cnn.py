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
learning_rate = 0.0001
regularization_rate = 0.01
training_epochs = 20
batch_size = 100
display_step = 100
# total_steps = 100000

# 方便测试
total_steps = {TOTAL_STEPS}

# Network Parameters
n_input = 784 # Number of feature
n_classes = 10 # Number of classes to predict


# checkpoint 目录
logs_train_dir = "./checkpoint/"


def weight_variable(shape):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial)


def bias_variable(shape):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial)


def conv2d(x, W):
    # stride [1, x_movement, y_movement, 1]
    # Must have strides[0] = strides[3] = 1
    return tf.nn.conv2d(x, W, strides=[1, 1, 1, 1], padding='SAME')


def max_pool_2x2(x):
    # stride [1, x_movement, y_movement, 1]
    return tf.nn.max_pool(x, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')


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

            # Define variables
            x = tf.placeholder(tf.float32, [None, n_input])
            y_ = tf.placeholder(tf.float32, [None, 10])

            keep_prob = tf.placeholder(tf.float32)
            x_image = tf.reshape(x, [-1, 28, 28, 1])

            # Create the model...
            # Store layers weight & bias

            # params
            W_conv1 = weight_variable([5, 5, 1, 32]) # patch 5x5, in size 1, out size 32
            b_conv1 = bias_variable([32])
            ## conv1 layer ##
            h_conv1 = tf.nn.relu(conv2d(x_image, W_conv1) + b_conv1) # output size 28x28x32
            h_pool1 = max_pool_2x2(h_conv1) # output size 14x14x32

            # params
            W_conv2 = weight_variable([5, 5, 32, 64]) # patch 5x5, in size 32, out size 64
            b_conv2 = bias_variable([64])
            ## conv2 layer ##
            h_conv2 = tf.nn.relu(conv2d(h_pool1, W_conv2) + b_conv2) # output size 14x14x64
            h_pool2 = max_pool_2x2(h_conv2) # output size 7x7x64

            # params
            W_fc1 = weight_variable([7*7*64, 80])
            b_fc1 = bias_variable([80])
            # [n_samples, 7, 7, 64] ->> [n_samples, 7*7*64]
            ## fc1 layer ##
            h_pool2_flat = tf.reshape(h_pool2, [-1, 7*7*64])
            h_fc1 = tf.nn.relu(tf.matmul(h_pool2_flat, W_fc1) + b_fc1)
            h_fc1_drop = tf.nn.dropout(h_fc1, keep_prob)

            # params
            W_fc2 = weight_variable([80, 10])
            b_fc2 = bias_variable([10])

            ## fc2 layer ##
            h_fc2 = tf.matmul(h_fc1_drop, W_fc2) + b_fc2

            # Define operations
            pred = tf.nn.softmax(h_fc2)

            # the error between prediction and real data
            cost = tf.reduce_mean(-tf.reduce_sum(y_ * tf.log(pred), reduction_indices=[1]))       # loss
            global_step = tf.Variable(0)

            train_op = tf.train.AdamOptimizer(learning_rate).minimize(cost, global_step=global_step)

            # Test trained model
            correct_prediction = tf.equal(tf.argmax(pred, 1), tf.argmax(y_, 1))
            accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
  
            saver = tf.train.Saver()
            summary_op = tf.summary.merge_all()
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
        file_name = "/mnt/" + socket.gethostname() + "_" + str(
            FLAGS.job_name) + "_" + str(FLAGS.task_index) + "_time.txt"
        starttime = datetime.datetime.now()
        f1 = open(file_name,'w')
        f1.write(str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        f1.write("\n")
        f1.close()

        step = 0
        while not sv.should_stop() and step < total_steps:
            batch_xs, batch_ys = mnist.train.next_batch(batch_size)
            _, loss_v, step = sess.run([train_op, cost, global_step], feed_dict={x: batch_xs, y_: batch_ys, keep_prob: 0.5})
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
                                                             y_: mnist.test.labels}))
if __name__ == "__main__":
    tf.app.run()

