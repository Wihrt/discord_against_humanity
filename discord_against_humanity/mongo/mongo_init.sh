#!/bin/bash -x

while read line
do
    if [ $(echo $line | egrep ^# | wc -l) -eq 0 ]
    then
        options=""
        db=$(echo $line | cut -d ";" -f 1)
        collection=$(echo $line | cut -d ";" -f 2)
        file=$(echo $line | cut -d ";" -f 3)
        json_array=$(echo $line | cut -d ";" -f 4)

        if [ $json_array == true ]
        then
            options="$options --jsonArray"
        fi
        mongoimport --db $db --collection $collection --file $file $options
    fi
done < /docker-entrypoint-initdb.d/imports.txt