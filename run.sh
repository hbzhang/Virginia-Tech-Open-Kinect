source conf.d/default
source conf.d/custom

rm kill.sh

if [[ -n ${DB_PORT} ]]; then
  DB_PORT_ARG="--port $DB_PORT"
else
  DB_PORT_ARG="" 
fi 

if [[ -n ${DB_SAVE} ]]; then
  DB_SAVE_ARG="--save $DB_SAVE"
else
  DB_SAVE_ARG=""
fi

python src/sql_server.py $DB_PORT_ARG $DB_SAVE_ARG >> $LOG_FILE 2>&1 &
echo "kill $!" >> kill.sh
echo "echo Stopped Database" >> kill.sh
echo Started Database

if [[ -n ${FILTER_PORT} ]]; then
  FILTER_PORT_ARG="--port $FILTER_PORT"
else
  FILTER_PORT_ARG=""
fi

if [[ -n ${FILTER_RULE_FILE} ]]; then
  FILTER_RULE_FILE_ARG="--rule $FILTER_RULE_FILE"
else
  FILTER_RULE_FILE_ARG=""
fi

python src/filter_server.py $FILTER_PORT_ARG $FILTER_RULE_FILE_ARG >> $LOG_FILE 2>&1 &
echo "kill $!" >> kill.sh
echo "echo Stopped Filter" >> kill.sh
echo Started Filter 

bad_kill_command="echo \"Servers could not be shutoff. Are they running?\""
write_kill_command="echo $bad_kill_command > kill.sh"
echo $write_kill_command >> kill.sh
chmod u+x kill.sh
