Vagrant.configure("2") do |config|
  config.vm.box = "debian/stretch64"

  config.vm.provision :docker
  config.vm.provision :docker_compose, yml: "/vagrant/docker-compose.yml", rebuild: true, run: "always"

  config.vm.network "forwarded_port", guest: 5222, host: 5222
  config.vm.network "forwarded_port", guest: 5280, host: 5280

  config.vm.post_up_message = "Development box for the 0ad lobby.

Run 'vagrant ssh' and 'cd /vagrant && docker-compose ps' afterwards to
see the list of running containers."

end
