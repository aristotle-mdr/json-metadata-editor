document.item_registry = {
  items: {},
  all: function() {
    var x = [];
    for (var i in this.items){x.push(this.items[i])}
    return x
  },
  of_type: function(type) {
    return this.all().filter(function(x) {
      return x.item_type === type;
    })
  },
  update: function(key, value) {
    this.items[key] = value;
  }
};

var $extend = $.extend;

JSONEditor.defaults.editors.local_metadata = JSONEditor.defaults.editors.object.extend({
  onChildEditorChange: function(editor) {
    this._super(editor);
    var subtype = "";
    if(this.parent.schema.options && this.parent.schema.options.type) subtype = this.parent.schema.options.type
    console.log(this);
    document.item_registry.update(this.path, {
      'uuid':'local##'+this.path, 'item_type': subtype ,
      'id':null, 'title': this.value.name, 'text': this.value.definition, "value": this.value
    });
  },
});