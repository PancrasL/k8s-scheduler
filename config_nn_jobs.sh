# produce uuid
# jobid=$(uuidgen)

# config job yaml
# echo $jobid

# the tf cluster's start number and end number
start_number=${1}
end_number=${2}

ps_number=${3}
pod_container_port=${4}

create_job_dir=${5}
nn=${6}

wk_number=$(echo ${end_number}-${start_number}-${ps_number}+1|bc)

echo "the start number: ${start_number}"
echo "the end number: ${end_number}"

echo "the ps number: ${ps_number}"
echo "the wk number: ${wk_number}"

echo "the pod_container_port: ${pod_container_port}"
echo "create the new tf job folder: ${create_job_dir}"

# delete_jobs.sh
touch ./template/delete_all_${start_number}.sh

#create new job folder
mkdir -p ./jobs/${create_job_dir}

# tf job config
# python_codeblock="python gradient_descent.py"
python_codeblock="python "$nn
check_port_command=""

j=0
service_index=$start_number
service_port=$(expr ${pod_container_port} + $start_number)
while [ $j -lt $ps_number ]
do
    if [ $j -eq 0 ]
    then
        python_codeblock=$python_codeblock" --ps_hosts=tensorflow-ps-service${service_index}.default.svc.cluster.local:2222,"
    else
        python_codeblock=$python_codeblock"tensorflow-ps-service${service_index}.default.svc.cluster.local:2222,"
    fi
    check_port_command=$check_port_command"test=3; while [ \$test != 0 ]; do test=\$(nc -zv -w 2 tensorflow-ps-service${service_index}.default.svc.cluster.local 2222; echo \$?;); echo \$test; done; "
    service_index=$(expr $service_index + 1)
    service_port=$(expr $service_port + 1)
    j=$(expr $j + 1)
done

#remove the comma
python_codeblock=${python_codeblock%?}

j=0
while [ $j -lt $wk_number ]
do
    if [ $j -eq 0 ]
    then
        python_codeblock=$python_codeblock" --worker_hosts=tensorflow-wk-service${service_index}.default.svc.cluster.local:2222,"
    else
        python_codeblock=$python_codeblock"tensorflow-wk-service${service_index}.default.svc.cluster.local:2222,"
    fi
    check_port_command=$check_port_command"test=3; while [ \$test != 0 ]; do test=\$(nc -zv -w 2 tensorflow-wk-service${service_index}.default.svc.cluster.local 2222; echo \$?;); echo \$test; done; "
    service_index=$(expr $service_index + 1)
    service_port=$(expr $service_port + 1)
    j=$(expr $j + 1)
done
#remove the comma
python_codeblock=${python_codeblock%?}

# ps config
i=0
ps_number_end=${start_number}
while [ `echo "${i} < ${ps_number}" | bc` -eq 1 ]
do
    port=$(echo ${pod_container_port}+${ps_number_end}|bc)
    #config ps pod
    cp ./template/ps_pod.yaml ./template/ps_pod${ps_number_end}.yaml
    # sed -i 's/{{job-id}}/'$jobid'/' ./template/ps_pod${ps_number_end}.yaml
    sed -i 's/{{ps_pod_index}}/'$ps_number_end'/g' ./template/ps_pod${ps_number_end}.yaml
    sed -i 's/{{ps_port_index}}/'$port'/' ./template/ps_pod${ps_number_end}.yaml

    # config tf ps
    python_codeblock_temp=$python_codeblock" --job_name=ps --task_index=${i} 1>ps_log_${i} 2>ps_errlog_${i};"
    sed -i 's/{{check_port_communicate}}/'"$check_port_command"'/' ./template/ps_pod${ps_number_end}.yaml
    sed -i 's/{{python_codeblock_template}}/'"$python_codeblock_temp"'/' ./template/ps_pod${ps_number_end}.yaml

    mv ./template/ps_pod${ps_number_end}.yaml ./jobs/${create_job_dir}

    # config delete ps job
    # echo "kubectl delete job tf-ps-1-2-${ps_number_end}-${jobid}" >> ./template/delete_all_${start_number}.sh
    echo "kubectl delete job tf-ps-1-2-${ps_number_end}" >> ./template/delete_all_${start_number}.sh

    #config ps service
    cp ./template/ps_service.yaml ./template/ps_service${ps_number_end}.yaml
    sed -i 's/{{ps_service_index}}/'$ps_number_end'/' ./template/ps_service${ps_number_end}.yaml
    sed -i 's/{{ps_service_port}}/'$port'/' ./template/ps_service${ps_number_end}.yaml
    mv ./template/ps_service${ps_number_end}.yaml ./jobs/${create_job_dir}

    # config delete ps service
    echo "kubectl delete svc tensorflow-ps-service${ps_number_end}" >> ./template/delete_all_${start_number}.sh

    ps_number_end=$(expr $ps_number_end + 1)
    i=$(expr $i + 1)
done


#wk config
wk_number_end=${ps_number_end}
i=0
while [ `echo "${i} < ${wk_number}" | bc` -eq 1 ]
do
    port=$(echo ${pod_container_port}+${wk_number_end}|bc)
    #config wk pod
    cp ./template/wk_pod.yaml ./template/wk_pod${wk_number_end}.yaml
    # sed -i 's/{{job-id}}/'$jobid'/' ./template/wk_pod${wk_number_end}.yaml
    sed -i 's/{{wk_pod_index}}/'$wk_number_end'/' ./template/wk_pod${wk_number_end}.yaml
    sed -i 's/{{wk_port_index}}/'$port'/' ./template/wk_pod${wk_number_end}.yaml
    
    # config tf wk
    python_codeblock_temp=$python_codeblock" --job_name=worker --task_index=${i} 1>worker_log_${i} 2>worker_errlog_${i};"
    sed -i 's/{{check_port_communicate}}/'"$check_port_command"'/' ./template/wk_pod${wk_number_end}.yaml
    sed -i 's/{{python_codeblock_template}}/'"$python_codeblock_temp"'/' ./template/wk_pod${wk_number_end}.yaml

    # config wk's workspace, fixme: if there exists many ps servers, then the first ps downloads and creates the shared folder, other ps servers and workers just change workspace to the shared folder 
    # change_workspace_to_shared_folder_cmd="while [ ! -d './distribute-ML-demo-master-$start_number/' ]; do sleep 1; done; cd ./distribute-ML-demo-master-$start_number/;"
    change_workspace_to_shared_folder_cmd="cd ./distribute-ML-demo-master-$start_number/;"
    sed -i 's|{{change_workspace_to_shared_folder}}|'"$change_workspace_to_shared_folder_cmd"'|' ./template/wk_pod${wk_number_end}.yaml

    mv ./template/wk_pod${wk_number_end}.yaml ./jobs/${create_job_dir}

    # config delete wk job
    # echo "kubectl delete job tf-wk-1-2-${wk_number_end}-${jobid}" >> ./template/delete_all_${start_number}.sh
    echo "kubectl delete job tf-wk-1-2-${wk_number_end}" >> ./template/delete_all_${start_number}.sh

    # config wk service
    cp ./template/wk_service.yaml ./template/wk_service${wk_number_end}.yaml
    sed -i 's/{{wk_service_index}}/'$wk_number_end'/' ./template/wk_service${wk_number_end}.yaml
    sed -i 's/{{wk_service_port}}/'$port'/' ./template/wk_service${wk_number_end}.yaml
    mv ./template/wk_service${wk_number_end}.yaml ./jobs/${create_job_dir}

    # config delete wk service
    echo "kubectl delete svc tensorflow-wk-service${wk_number_end}" >> ./template/delete_all_${start_number}.sh

    wk_number_end=$(expr $wk_number_end + 1)
    i=$(expr $i + 1)
done


# chmod
chmod +x ./template/delete_all_${start_number}.sh
mv ./template/delete_all_${start_number}.sh ./delete_all/

# sed -i 's/{{job-id}}/'$jobid'/' ./template/delete_all.sh
# mv ./template/delete_all.sh ./scripts/
# chmod +x ./scripts/delete_all.sh

# # start job and svc
# kubectl create -f ./jobs/tf_job.yaml
