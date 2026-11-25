function money(cents) {
  if (cents === null || cents === undefined) return '¥0.00'
  return '¥' + (cents / 100).toFixed(2)
}

function dateAdd(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  const m = ('0' + (d.getMonth() + 1)).slice(-2)
  const day = ('0' + d.getDate()).slice(-2)
  return d.getFullYear() + '-' + m + '-' + day
}

function statusType(status) {
  return {
    '待就诊': 'blue', '已完成': 'amber', '待支付': 'amber', '已结算': 'green',
    '已退款': 'red', '已取消': '', '待确认': 'amber', '已确认': 'green', '已过期': ''
  }[status] || ''
}

module.exports = { money, dateAdd, statusType }
