const mapLNDomain = obj => {
  obj.date = Quasar.date.formatDate(new Date(obj.time), 'YYYY-MM-DD HH:mm')

  obj.displayUrl = ['/lnaddress/', obj.id].join('')
  return obj
}

window.app = Vue.createApp({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      domains: [],
      addresses: [],
      domainDialog: {
        show: false,
        data: {}
      },
      domainsTable: {
        columns: [
          {name: 'id', align: 'left', label: 'ID', field: 'id'},
          {
            name: 'domain',
            align: 'left',
            label: 'Domain name',
            field: 'domain'
          },
          {name: 'wallet', align: 'left', label: 'Wallet', field: 'wallet'},
          {
            name: 'webhook',
            align: 'left',
            label: 'Webhook',
            field: 'webhook'
          },
          {
            name: 'cost',
            align: 'left',
            label: 'Cost Per Day',
            field: 'cost'
          }
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      addressesTable: {
        columns: [
          {
            name: 'username',
            align: 'left',
            label: 'Alias/username',
            field: 'username'
          },
          {
            name: 'domain',
            align: 'left',
            label: 'Domain name',
            field: 'domain'
          },
          {
            name: 'email',
            align: 'left',
            label: 'Email',
            field: 'email'
          },
          {
            name: 'sats',
            align: 'left',
            label: 'Sats paid',
            field: 'sats'
          },
          {
            name: 'duration',
            align: 'left',
            label: 'Duration in days',
            field: 'duration'
          },
          {name: 'id', align: 'left', label: 'ID', field: 'id'}
        ],
        pagination: {
          rowsPerPage: 10
        }
      }
    }
  },
  methods: {
    getDomains() {
      LNbits.api
        .request(
          'GET',
          '/lnaddress/api/v1/domains?all_wallets=true',
          this.g.user.wallets[0].inkey
        )
        .then(response => {
          this.domains = response.data.map(function (obj) {
            return mapLNDomain(obj)
          })
        })
    },
    sendFormData() {
      const wallet = _.findWhere(this.g.user.wallets, {
        id: this.domainDialog.data.wallet
      })
      const data = this.domainDialog.data
      if (data.id) {
        this.updateDomain(wallet, data)
      } else {
        this.createDomain(wallet, data)
      }
    },
    createDomain(wallet, data) {
      console.log(data)
      LNbits.api
        .request('POST', '/lnaddress/api/v1/domains', wallet.adminkey, data)
        .then(response => {
          this.domains.push(mapLNDomain(response.data))
          this.domainDialog.show = false
          this.domainDialog.data = {}
        })
        .catch(error => {
          LNbits.utils.notifyApiError(error)
        })
    },
    updateDomainDialog(formId) {
      const link = _.findWhere(this.domains, {id: formId})
      this.domainDialog.data = _.clone(link)
      this.domainDialog.show = true
    },
    updateDomain(wallet, data) {
      if (!data.webhook) {
        delete data.webhook
      }
      LNbits.api
        .request(
          'PUT',
          '/lnaddress/api/v1/domains/' + data.id,
          wallet.adminkey,
          data
        )
        .then(response => {
          this.domains = _.reject(this.domains, function (obj) {
            return obj.id == data.id
          })
          this.domains.push(mapLNDomain(response.data))
          this.domainDialog.show = false
          this.domainDialog.data = {}
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    deleteDomain(domainId) {
      const domains = _.findWhere(this.domains, {id: domainId})
      LNbits.utils
        .confirmDialog('Are you sure you want to delete this domain link?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/lnaddress/api/v1/domains/' + domainId,
              _.findWhere(this.g.user.wallets, {id: domains.wallet}).inkey
            )
            .then(response => {
              this.domains = _.reject(self.domains, function (obj) {
                return obj.id == domainId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    exportDomainsCSV() {
      LNbits.utils.exportCSV(this.domainsTable.columns, this.domains)
    },

    //ADDRESSES

    getAddresses() {
      LNbits.api
        .request(
          'GET',
          '/lnaddress/api/v1/addresses?all_wallets=true',
          this.g.user.wallets[0].inkey
        )
        .then(response => {
          this.addresses = response.data
            .filter(d => d.paid)
            .map(function (obj) {
              // obj.domain_name = this.domains.find(d => d.id == obj.domain)
              return mapLNDomain(obj)
            })
          console.log(this.addresses)
        })
    },
    deleteAddress(addressId) {
      const addresses = _.findWhere(this.addresses, {id: addressId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this LN address')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/lnaddress/api/v1/addresses/' + addressId,
              _.findWhere(this.g.user.wallets, {id: addresses.wallet}).inkey
            )
            .then(response => {
              this.addresses = _.reject(self.addresses, function (obj) {
                return obj.id == addressId
              })
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error)
            })
        })
    },
    exportAddressesCSV() {
      LNbits.utils.exportCSV(this.addressesTable.columns, this.addresses)
    }
  },
  created() {
    if (this.g.user.wallets.length) {
      this.getDomains()
      this.getAddresses()
    }
  }
})
