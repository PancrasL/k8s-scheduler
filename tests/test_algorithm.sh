# shell_name start end ps_number container_start_port job's_folder tf_code_file_name
dir=$(cd $(dirname $0); pwd)
cd dir/../
sh ./config_nn_jobs.sh 0 2 1 2222 local-test dnn3.py 

