# shell_name start end ps_number container_start_port job's_folder tf_code_file_name


set -xeuo pipefail

dir=$(cd $(dirname $0); pwd)
cd dir/../
sh ./config_nn_jobs.sh 0 8 3 2222 test1 dnn3.py 
python schedule.py test1 kubernetes
