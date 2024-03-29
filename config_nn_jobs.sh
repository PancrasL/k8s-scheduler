# produce uuid
# jobid=$(uuidgen)

# config job yaml
# echo $jobid

# the tf cluster's start number and end number
start_number=${1}
end_number=${2}

ps_number=${3}
pod_container_port=${4}

cluster_name=${5}
nn=${6}

wk_number=$(echo ${end_number}-${start_number}-${ps_number}+1|bc)

echo "the start number: ${start_number}"
echo "the end number: ${end_number}"

echo "the ps number: ${ps_number}"
echo "the wk number: ${wk_number}"

echo "the pod_container_port: ${pod_container_port}"
echo "create the new tf job folder: ${cluster_name}"

# if the tf job folder exists，delete it
if [ -d "./jobs/${cluster_name}" ];then
rm -rf ./jobs/${cluster_name}
fi

# create delete_jobs.sh
touch ./template/delete_all_${cluster_name}.sh

#create new job folder
mkdir -p ./jobs/${cluster_name}

#--------------------------------------------------------------------------------#
##添加ps的地址
python_codeblock="python "$nn
python_file_exists="while [ ! -f '$nn' ]; do sleep 1; done;"
j=0
service_index=$start_number
while [ $j -lt $ps_number ]
do
    if [ $j -eq 0 ]
    then
        python_codeblock=$python_codeblock" --ps_hosts=tensorflow-ps-service-${cluster_name}-${service_index}.default.svc.cluster.local:2222,"
    else
        python_codeblock=$python_codeblock"tensorflow-ps-service-${cluster_name}-${service_index}.default.svc.cluster.local:2222,"
    fi
    service_index=$(expr $service_index + 1)
    j=$(expr $j + 1)
done

#移除逗号
python_codeblock=${python_codeblock%?}

#添加worker的地址
j=0
while [ $j -lt $wk_number ]
do
    if [ $j -eq 0 ]
    then
        python_codeblock=$python_codeblock" --worker_hosts=tensorflow-wk-service-${cluster_name}-${service_index}.default.svc.cluster.local:2222,"
    else
        python_codeblock=$python_codeblock"tensorflow-wk-service-${cluster_name}-${service_index}.default.svc.cluster.local:2222,"
    fi
    service_index=$(expr $service_index + 1)
    j=$(expr $j + 1)
done
#移除逗号
python_codeblock=${python_codeblock%?}

#--------------------------------------------------------------------------------#
##配置ps的yaml文件
i=0
ps_number_end=${start_number}
while [ `echo "${i} < ${ps_number}" | bc` -eq 1 ]
do
    #config ps pod
    cp ./template/ps_pod.yaml ./template/ps_pod${ps_number_end}.yaml
    sed -i 's/{{ps_pod_index}}/'$ps_number_end'/g' ./template/ps_pod${ps_number_end}.yaml
    sed -i 's/{{cluster_name}}/'$cluster_name'/g' ./template/ps_pod${ps_number_end}.yaml
    sed -i 's/{{python_file_exists}}/'"$python_file_exists"'/g' ./template/ps_pod${ps_number_end}.yaml

    # config tf ps
    python_codeblock_temp=$python_codeblock" --job_name=ps --task_index=${i} 1>ps_log_${i} 2>ps_errlog_${i};"
    sed -i 's/{{python_codeblock_template}}/'"$python_codeblock_temp"'/' ./template/ps_pod${ps_number_end}.yaml
    # config shared folder
    ps_change_workplace_to_shared_folder=""
    if [ ${ps_number_end} -eq ${start_number} ]; then 
        ps_change_workplace_to_shared_folder="if [ ! -d '/mnt/distribute-ML-demo-master-$cluster_name/' ]; then curl ftp://192.168.0.10/distribute-ML-code.zip > qw.zip; unzip qw.zip; mv ./distribute-ML-code/ ./distribute-ML-demo-master-$cluster_name/;mv ./distribute-ML-demo-master-$cluster_name/ /mnt/;cd /mnt/distribute-ML-demo-master-$cluster_name/; else cd /mnt/distribute-ML-demo-master-$cluster_name/; fi;"
    else
        ps_change_workplace_to_shared_folder="cd /mnt/; while [ ! -d './distribute-ML-demo-master-$cluster_name/' ]; do sleep 1; done; cd ./distribute-ML-demo-master-$cluster_name/;"
    fi
    sed -i 's|{{ps_change_workplace_to_shared_folder}}|'"$ps_change_workplace_to_shared_folder"'|' ./template/ps_pod${ps_number_end}.yaml

    mv ./template/ps_pod${ps_number_end}.yaml ./jobs/${cluster_name}

    # config delete ps job
    echo "kubectl delete job tf-ps-${cluster_name}-${ps_number_end}" >> ./template/delete_all_${cluster_name}.sh

    #config ps service
    cp ./template/ps_service.yaml ./template/ps_service${ps_number_end}.yaml
    sed -i 's/{{ps_service_index}}/'$ps_number_end'/' ./template/ps_service${ps_number_end}.yaml
    sed -i 's/{{cluster_name}}/'$cluster_name'/' ./template/ps_service${ps_number_end}.yaml
    mv ./template/ps_service${ps_number_end}.yaml ./jobs/${cluster_name}

    

    # config delete ps service
    echo "kubectl delete svc tensorflow-ps-service-${cluster_name}-${ps_number_end}" >> ./template/delete_all_${cluster_name}.sh

    ps_number_end=$(expr $ps_number_end + 1)
    i=$(expr $i + 1)
done

#--------------------------------------------------------------------------------#
##配置worker的yaml文件
wk_number_end=${ps_number_end}
i=0
while [ `echo "${i} < ${wk_number}" | bc` -eq 1 ]
do
    #config wk pod
    cp ./template/wk_pod.yaml ./template/wk_pod${wk_number_end}.yaml
    sed -i 's/{{wk_pod_index}}/'$wk_number_end'/' ./template/wk_pod${wk_number_end}.yaml
    sed -i 's/{{cluster_name}}/'$cluster_name'/g' ./template/wk_pod${wk_number_end}.yaml
    sed -i 's/{{python_file_exists}}/'"$python_file_exists"'/g' ./template/wk_pod${wk_number_end}.yaml

    # config tf wk
    python_codeblock_temp=$python_codeblock" --job_name=worker --task_index=${i} 1>worker_log_${i} 2>worker_errlog_${i};"
    sed -i 's/{{python_codeblock_template}}/'"$python_codeblock_temp"'/' ./template/wk_pod${wk_number_end}.yaml

    # config wk's workspace, fixme: if there exists many ps servers, then the first ps downloads and creates the shared folder, other ps servers and workers just change workspace to the shared folder 
    change_workspace_to_shared_folder_cmd="while [ ! -d './distribute-ML-demo-master-$cluster_name/' ]; do sleep 1; done; cd ./distribute-ML-demo-master-$cluster_name/;"
    sed -i 's|{{change_workspace_to_shared_folder}}|'"$change_workspace_to_shared_folder_cmd"'|' ./template/wk_pod${wk_number_end}.yaml

    mv ./template/wk_pod${wk_number_end}.yaml ./jobs/${cluster_name}

    # config delete wk job
    echo "kubectl delete job tf-wk-${cluster_name}-${wk_number_end}" >> ./template/delete_all_${cluster_name}.sh

    # config wk service
    cp ./template/wk_service.yaml ./template/wk_service${wk_number_end}.yaml
    sed -i 's/{{wk_service_index}}/'$wk_number_end'/' ./template/wk_service${wk_number_end}.yaml
    sed -i 's/{{cluster_name}}/'$cluster_name'/' ./template/wk_service${wk_number_end}.yaml

    mv ./template/wk_service${wk_number_end}.yaml ./jobs/${cluster_name}

    # config delete wk service
    echo "kubectl delete svc tensorflow-wk-service-${cluster_name}-${wk_number_end}" >> ./template/delete_all_${cluster_name}.sh

    wk_number_end=$(expr $wk_number_end + 1)
    i=$(expr $i + 1)
done


# chmod
chmod +x ./template/delete_all_${cluster_name}.sh
mv ./template/delete_all_${cluster_name}.sh ./delete_all/
