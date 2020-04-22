# shell_name start end ps_number container_start_port job's_folder tf_code_file_name

dir=$(cd $(dirname $0); pwd)
cd dir/../

# ps: 3  worker: 5
sh ./config_nn_jobs.sh 0 8 3 2222 test1 dnn3.py 
python schedule.py test1 suitable
sleep 15

# ps: 2  worker: 4
sh ./config_nn_jobs.sh 0 8 3 2222 test2 dnn3.py 
python schedule.py test2 suitable
sleep 15

# ps: 1  worker: 3
sh ./config_nn_jobs.sh 0 8 3 2222 test3 dnn3.py 
python schedule.py test3 suitable
sleep 15