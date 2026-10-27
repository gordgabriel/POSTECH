# Infraestrutura

O Terraform versionado fica em `infra/terraform`. Para a fase 2 local, use `environments/local-kind` e `environments/local-postgres`. Os ambientes existentes de VPC/S3 e a alternativa de AWS (`environments/aws-k8s`) permanecem separados.

## Ambiente local: Kind e PostgreSQL

Para a fase 2, `environments/local-kind` cria um cluster Kind chamado `postech-iac`; `environments/local-postgres` conecta a esse kubeconfig e cria o PostgreSQL, seu PVC, Service, namespace e Secrets. O metrics-server é instalado pelo Helm para que o HPA da API receba métricas de CPU. Nenhuma credencial AWS é necessária. O cluster `postech` criado manualmente anteriormente não é importado, modificado nem removido.

São dois estados Terraform intencionais: o primeiro cria o cluster e o kubeconfig; o segundo usa o kubeconfig para criar recursos dentro do cluster. Aplique e destrua os stacks nessa ordem. O PostgreSQL fica sob gestão Terraform, enquanto a Application `postech-api-iac` do Argo CD gerencia apenas a API em `k8s/overlays/local-iac`. O cluster antigo `postech` mantém sua Application `postech-api` e overlay `k8s/overlays/kind`.

O Secret contém senhas geradas pelo provider `random_password` e por isso também existe em texto claro no state Terraform. Mantenha o state local fora do Git e proteja-o como credencial. O PVC usa a StorageClass padrão do Kind (`local-path`) e os dados são locais e descartáveis; destruir o stack de workloads apaga o banco. O lock file de cada ambiente deve ser versionado para fixar as versões dos providers.

O metrics-server usa `--kubelet-insecure-tls` por causa dos certificados de kubelet gerados pelo Kind. Essa configuração é exclusiva para laboratório; em produção, configure a CA de kubelet e um backend de secrets apropriado.

## Executar o ambiente local

Pré-requisitos: Docker Desktop usando Linux containers, Terraform CLI e `kubectl`. Execute os comandos na raiz do repositório, no PowerShell. O provider `tehcyx/kind` cria o cluster usando a biblioteca Kind e a API do Docker; não execute `kind create cluster` manualmente para esse stack. O CLI `kind` é opcional para inspeção.

```powershell
$kindDir = "infra/terraform/environments/local-kind"
$postgresDir = "infra/terraform/environments/local-postgres"

terraform -chdir=$kindDir init
terraform -chdir=$kindDir plan
terraform -chdir=$kindDir apply
$env:KUBECONFIG = terraform -chdir=$kindDir output -raw kubeconfig_path
kubectl get nodes

terraform -chdir=$postgresDir init
terraform -chdir=$postgresDir plan
terraform -chdir=$postgresDir apply
kubectl get pods,pvc -n postech
kubectl top pods -n postech
```

Revise cada `plan` antes de confirmar `apply`. O primeiro estado cria apenas o cluster e grava o kubeconfig local em `local-kind/kubeconfig`; o segundo usa esse arquivo para criar os recursos dentro dele. O kubeconfig e os states contêm credenciais e estão ignorados pelo Git.

Depois, instale o Argo CD no cluster conforme o README principal e aplique `k8s/argocd/application-local-iac.yaml`. O Argo CD gerencia a API; o Terraform continua sendo o único responsável por namespace, Secret e PostgreSQL.

Para remover o ambiente, destrua primeiro os workloads e depois o cluster, usando os mesmos diretórios e states:

```powershell
terraform -chdir=$postgresDir destroy
terraform -chdir=$kindDir destroy
Remove-Item Env:KUBECONFIG
```

O destroy do segundo estado apaga o PVC e os dados do PostgreSQL. O destroy do primeiro remove o cluster Kind `postech-iac`, não o cluster preexistente `postech`.

## EKS e PostgreSQL

O ambiente `infra/terraform/environments/aws-k8s` cria:

- VPC com duas sub-redes públicas e duas privadas, distribuídas entre zonas de disponibilidade.
- Cluster EKS com um grupo gerenciado de nós EC2. Para evitar o custo recorrente de NAT Gateway no laboratório, os nós ficam nas sub-redes públicas e recebem IP público; o endpoint público da API EKS é restrito ao CIDR informado em `terraform.tfvars`.
- RDS PostgreSQL privado, acessível na porta 5432 apenas pelo security group do cluster EKS. A senha master é gerenciada pelo RDS e armazenada no Secrets Manager.
- Tags de sub-rede para descoberta de load balancers do Kubernetes.

Essa configuração é para laboratório, não produção. O banco não tem Multi-AZ e `skip_final_snapshot = true`, então destruir o ambiente apaga os dados. Os nós EC2 são públicos, embora o RDS permaneça em sub-redes privadas. Para produção, use nós privados, NAT ou endpoints VPC, backup final, proteção contra exclusão, políticas IAM revisadas e acesso privado ou fortemente restrito ao endpoint EKS.

## Pré-requisitos e criação

É necessário ter Terraform, AWS CLI e credenciais AWS configuradas para uma conta/região com permissões para VPC, EKS, EC2, IAM, RDS e Secrets Manager. O backend é local neste exemplo: não compartilhe o `terraform.tfstate` nem o diretório `.terraform`.

No PowerShell:

```powershell
Set-Location infra/terraform/environments/aws-k8s
Copy-Item terraform.tfvars.example terraform.tfvars
```

Edite `terraform.tfvars` e troque o IP de exemplo pelo seu IPv4 público de administração, com máscara `/32`. Antes de criar qualquer recurso, execute:

```powershell
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan
```

Revise o plano e os preços da região antes de executar `terraform apply`. Não faça `apply` sem entender os custos e confirmar a conta AWS selecionada. EKS cobra pelo plano de controle por hora; também há custos para EC2, armazenamento dos nós, RDS, armazenamento/backups, endereços IPv4 públicos e Secrets Manager. Não há NAT Gateway neste ambiente para reduzir custos, mas os recursos ainda geram cobrança enquanto existirem.

Após a criação, use o comando exibido em `terraform output -raw configure_kubectl`, depois valide com `kubectl get nodes`. O Terraform apenas cria EKS e RDS; não instala Argo CD nem configura a aplicação para o banco automaticamente.

## Conectar a API ao RDS

Faça estes passos no diretório `infra/terraform/environments/aws-k8s`, após criar a infraestrutura e configurar `kubectl` para o EKS:

1. Obtenha o endpoint e o usuário do banco:

	```powershell
	$dbHost = terraform output -raw database_address
	$dbUser = terraform output -raw database_username
	```

2. Substitua os dois valores `REPLACE_WITH_...` em `k8s/overlays/aws/rds-config-patch.yaml` por `$dbHost` e `$dbUser`. O endpoint não é uma credencial, mas use o overlay AWS somente no cluster EKS.
3. Crie o namespace e o Secret da aplicação a partir do secret master criado pelo RDS. A senha é lida em memória e não deve ser impressa, commitada ou colocada no ConfigMap:

	```powershell
	$secretArn = terraform output -raw database_master_secret_arn
	$rdsCredentials = aws secretsmanager get-secret-value --secret-id $secretArn --query SecretString --output text | ConvertFrom-Json
	$djangoSecret = python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
	kubectl create namespace postech --dry-run=client -o yaml | kubectl apply -f -
	kubectl create secret generic postech-secrets -n postech `
	  --from-literal=SECRET_KEY=$djangoSecret `
	  --from-literal=DB_PASSWORD=$rdsCredentials.password `
	  --dry-run=client -o yaml | kubectl apply -f -
	Remove-Variable rdsCredentials, djangoSecret, secretArn
	```

4. Se Argo CD ainda não estiver instalado no EKS, instale-o conforme o procedimento da documentação oficial. Depois aplique `kubectl apply -f k8s/argocd/application-aws.yaml` para apontar a Application `postech-api` para `k8s/overlays/aws`.
5. Commit e envie o overlay AWS já preenchido para `main`; Argo CD sincroniza Deployment e ConfigMap. Verifique com `kubectl get pods,hpa -n postech` e `kubectl logs deployment/postech-api -n postech`.

O PostgreSQL local é gerenciado por `environments/local-postgres`, não pelo overlay Kustomize. O overlay `kind` configura apenas a API para `DB_HOST=postech-db`. O overlay `aws` usa somente a API e o ConfigMap apontando para RDS, sem criar um banco dentro do EKS. Não mantenha os overlays Kind e AWS ativos na mesma Application ao mesmo tempo: ambos gerenciam os mesmos recursos `postech-api`.

A senha do RDS gerenciada pelo Secrets Manager é copiada para um Kubernetes Secret nesta configuração manual; rotação no Secrets Manager exige atualizar esse Secret e reiniciar os pods. Para produção, prefira External Secrets Operator ou Secrets Store CSI Driver com IAM Roles for Service Accounts/Pod Identity.

Para remover o laboratório, execute `terraform destroy` no mesmo diretório depois de confirmar a conta e a região. Como o snapshot final está desabilitado, isso remove o banco e seus dados.

O deploy Kubernetes local continua documentado no README principal e usa Kind; este ambiente Terraform AWS não é criado automaticamente pelo CI. O workflow apenas valida os arquivos, sem credenciais, `plan` ou `apply`.