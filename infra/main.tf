terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.region }
variable "region" { default = "us-east-2" }
variable "domain" { type = string }
variable "repository" { default = "https://github.com/aasimghanics-lab/fieldsense.git" }
variable "instance_type" { default = "t3.large" }
data "aws_vpc" "default" { default = true }
data "aws_subnets" "default" {
  filter {
    name = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}
data "aws_ami" "linux" {
  most_recent = true
  owners = ["amazon"]
  filter {
    name = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}
resource "aws_security_group" "web" {
  name_prefix = "fieldsense-"
  vpc_id = data.aws_vpc.default.id
  ingress {
    from_port = 80
    to_port = 80
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_iam_role" "host" {
  name_prefix = "fieldsense-host-"
  assume_role_policy = jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Principal={Service="ec2.amazonaws.com"},Action="sts:AssumeRole"}]})
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_instance_profile" "host" { role = aws_iam_role.host.name }
resource "aws_instance" "app" {
  ami = data.aws_ami.linux.id
  instance_type = var.instance_type
  subnet_id = sort(data.aws_subnets.default.ids)[0]
  vpc_security_group_ids = [aws_security_group.web.id]
  iam_instance_profile = aws_iam_instance_profile.host.name
  associate_public_ip_address = true
  metadata_options { http_tokens = "required" }
  root_block_device {
    volume_size = 40
    volume_type = "gp3"
    encrypted = true
  }
  user_data = templatefile("${path.module}/bootstrap.sh", {repository=var.repository, domain=var.domain})
  tags = { Name = "FieldSense" }
}
resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain = "vpc"
}
output "public_ip" { value = aws_eip.app.public_ip }
output "url" { value = "https://${var.domain}" }
output "instance_id" { value = aws_instance.app.id }
