Passo (Estado ASL),Tipo de Estado,Finalidade
1. TriggerDataBright,Task,Chama a Lambda que envia o POST à Data Bright e retorna o snapshot_id.
2. WaitForSnapshot,Wait,Pausa o fluxo por um tempo definido (ex: 2 minutos) para dar tempo à Data Bright de coletar os dados.
3. CheckSnapshotStatus,Task,"Chama a Lambda que usa o snapshot_id para consultar a Data Bright. Retorna {""status"": ""READY""} ou {""status"": ""PENDING""}."
4. IsDataReady,Choice,"O Cérebro do Loop: Verifica o status. Se READY, avança para o passo 5. Se PENDING, volta para o passo 2."
5. SaveDataToS3,Task,Chama a Lambda que finalmente baixa os dados do snapshot finalizado e os salva no seu S3 Bronze.