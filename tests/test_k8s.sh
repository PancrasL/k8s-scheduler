# shell_name start end ps_number container_start_port job's_folder tf_code_file_name

dir=$(cd $(dirname $0); pwd)
cd dir/../
schedule_mod="greedy"

# ps: 1  worker: 2  dnn2.py
cluster_name=k8s-test1
sh ./config_nn_jobs.sh 0 2 1 2222 $cluster_name dnn2.py 
python schedule.py $cluster_name $schedule_mod

# ps: 2  worker: 4  dnn4.py
cluster_name=k8s-test2
sh ./config_nn_jobs.sh 0 5 2 2222 $cluster_name dnn4.py 
python schedule.py $cluster_name $schedule_mod

# ps: 1  worker: 1  dnn1.py
cluster_name=k8s-test3
sh ./config_nn_jobs.sh 0 1 1 2222 $cluster_name dnn1.py 
python schedule.py $cluster_name $schedule_mod

# ps: 1  worker: 2  dnn3.py
cluster_name=k8s-test4
sh ./config_nn_jobs.sh 0 2 1 2222 $cluster_name dnn3.py 
python schedule.py $cluster_name $schedule_mod

# ps: 2  worker: 4  dnn4.py
cluster_name=k8s-test5
sh ./config_nn_jobs.sh 0 5 2 2222 $cluster_name dnn4.py 
python schedule.py $cluster_name $schedule_mod

# ps: 1  worker: 2  dnn3.py
cluster_name=k8s-test6
sh ./config_nn_jobs.sh 0 2 1 2222 $cluster_name dnn3.py 
python schedule.py $cluster_name $schedule_mod

# ps: 1  worker: 2  dnn2.py
cluster_name=k8s-test7
sh ./config_nn_jobs.sh 0 2 1 2222 $cluster_name dnn2.py 
python schedule.py $cluster_name $schedule_mod

# ps: 1  worker: 3  dnn4.py
cluster_name=k8s-test8
sh ./config_nn_jobs.sh 0 3 1 2222 $cluster_name dnn4.py 
python schedule.py $cluster_name $schedule_mod

# ps: 1  worker: 3  dnn2.py
cluster_name=k8s-test9
sh ./config_nn_jobs.sh 0 3 1 2222 $cluster_name dnn2.py 
python schedule.py $cluster_name $schedule_mod

# ps: 1  worker: 2  dnn1.py
cluster_name=k8s-test10
sh ./config_nn_jobs.sh 0 2 1 2222 $cluster_name dnn1.py 
python schedule.py $cluster_name $schedule_mod

# ps: 1  worker: 3  dnn2.py
cluster_name=k8s-test11
sh ./config_nn_jobs.sh 0 3 1 2222 $cluster_name dnn2.py 
python schedule.py $cluster_name $schedule_mod

# ps: 1  worker: 3  dnn2.py
cluster_name=k8s-test12
sh ./config_nn_jobs.sh 0 3 1 2222 $cluster_name dnn2.py 
python schedule.py $cluster_name $schedule_mod