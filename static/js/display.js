window.app = Vue.createApp({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      paymentReq: null,
      redirectUrl: null,
      formDialog: {
        show: false,
        data: {}
      },
      renewDialog: {
        show: false,
        data: {},
        info: false
      },
      receive: {
        show: false,
        status: 'pending',
        paymentReq: null
      },
      tab: 'create',
      wallet: {
        inkey: ''
      },
      cancelListener: () => {}
    }
  },
  computed: {
    amountSats() {
      let dialog = this.renewDialog.info ? this.renewDialog : this.formDialog
      if (!dialog.data.duration) return 0
      let sats = dialog.data.duration * parseInt('{{ domain_cost }}')
      dialog.data.sats = parseInt(sats)
      return sats
    },
    checkUsername: async function () {
      let username = this.formDialog.data.username
      if (!this.isValidUsername) {
        return true
      }
      let available = await axios
        .get(
          `/lnaddress/api/v1/address/availabity/${'{{domain_id}}'}/${username}`
        )
        .then(res => {
          return res.data < 1
        })
      console.log(available)
      return available
    },
    isValidUsername() {
      let username = this.formDialog.data.username
      return /^[a-z0-9_\.]+$/.test(username)
    }
  },
  methods: {
    resetForm(e) {
      e.preventDefault()
      this.formDialog.data = {}
      this.renewDialog.data = {}
      this.renewDialog.info = false
    },

    closeReceiveDialog() {
      let checker = this.startPaymentNotifier
      dismissMsg()
      if (this.tab == 'create') {
        clearInterval(paymentChecker)
      }
      setTimeout(function () {}, 10000)
    },
    getUserInfo() {
      let {username, wallet_key} = this.renewDialog.data
      axios
        .get(
          `/lnaddress/api/v1/address/{{ domain_domain }}/${username}/${wallet_key}`
        )
        .then(res => {
          if (res) {
            let dt = {}
            let result = new Date(res.data.time * 1000)
            dt.start = new Date(res.data.time * 1000)
            dt.expiration = moment(
              result.setDate(result.getDate() + res.data.duration)
            ).format('dddd, MMMM Do YYYY, h:mm:ss a')
            dt.domain = '{{domain_domain}}'
            dt.wallet_endpoint = res.data.wallet_endpoint
            this.renewDialog.data = {
              ...this.renewDialog.data,
              ...dt
            }
            this.renewDialog.info = true
            console.log(this.renewDialog)
          }
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
    },
    renewAddress() {
      let {data} = this.renewDialog
      data.duration = parseInt(data.duration)

      axios
        .put(
          '/lnaddress/api/v1/address/{{ domain_id }}/' +
            data.username +
            '/' +
            data.wallet_key,
          data
        )
        .then(response => {
          this.paymentReq = response.data.payment_request
          this.paymentCheck = response.data.payment_hash

          dismissMsg = this.$q.notify({
            timeout: 0,
            message: 'Waiting for payment...'
          })

          this.receive = {
            show: true,
            status: 'pending',
            paymentReq: this.paymentReq
          }
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error)
        })
      return
    },
    startPaymentNotifier() {
      this.cancelListener()

      this.cancelListener = LNbits.events.onInvoicePaid(
        this.wallet,
        payment => {
          this.receive = {
            show: false,
            status: 'complete',
            paymentReq: null
          }
          dismissMsg()

          this.renewDialog.data = {}
          this.renewDialog.info = false

          this.$q.notify({
            type: 'positive',
            message: 'Sent, thank you!',
            icon: 'thumb_up'
          })
        }
      )
    },
    submitInvoice() {
      let {data} = this.formDialog
      data.domain = '{{ domain_id }}'
      if (data.wallet_endpoint == '') {
        data.wallet_endpoint = null
      }
      data.wallet_endpoint = data.wallet_endpoint ?? '{{ root_url }}'
      data.duration = parseInt(data.duration)
      axios
        .post('/lnaddress/api/v1/address/{{ domain_id }}', data)
        .then(response => {
          this.paymentReq = response.data.payment_request
          this.paymentCheck = response.data.payment_hash

          dismissMsg = this.$q.notify({
            timeout: 0,
            message: 'Waiting for payment...'
          })

          this.receive = {
            show: true,
            status: 'pending',
            paymentReq: this.paymentReq
          }

          paymentChecker = setInterval(() => {
            axios
              .get(`/lnaddress/api/v1/addresses/${this.paymentCheck}`)
              .then(res => {
                console.log('pay_check', res.data)
                if (res.data.paid) {
                  clearInterval(paymentChecker)
                  this.receive = {
                    show: false,
                    status: 'complete',
                    paymentReq: null
                  }
                  dismissMsg()

                  console.log(this.formDialog)
                  this.formDialog.data = {}
                  this.$q.notify({
                    type: 'positive',
                    message: 'Sent, thank you!',
                    icon: 'thumb_up'
                  })
                  console.log('END')
                }
              })
              .catch(function (error) {
                console.log(error)
                LNbits.utils.notifyApiError(error)
              })
          }, 5000)
        })
        .catch(function (error) {
          console.log(error)
          LNbits.utils.notifyApiError(error)
        })
    }
  },
  created() {
    this.wallet.inkey = domain_wallet_inkey
    this.startPaymentNotifier()
  }
})
