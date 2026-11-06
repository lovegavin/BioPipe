// Developer DOM regression. Run ONLY on an empty canvas in an isolated test
// profile. This edits the canvas; it does not replace Explorer/WebView testing.
(async () => {
  const wait = async predicate => {
    const end = performance.now() + 10000;
    while (!predicate()) {
      if (performance.now() > end) throw Error('Canvas condition timed out');
      await new Promise(resolve => setTimeout(resolve, 25));
    }
  };
  const count = () => Number(document.querySelector('.canvas-meta').textContent.match(/\d+/)[0]);
  const results = [];
  for (let round = 0; round < 5; round++) {
    const empty = document.querySelector('.canvas-empty');
    if (!empty || count() !== 0) throw Error('An empty synthetic canvas is required');
    const element = round % 2 ? empty.querySelector('button') : empty;
    const bounds = element.getBoundingClientRect();
    const x = bounds.x + bounds.width / 2, y = bounds.y + bounds.height / 2;
    const target = document.elementFromPoint(x, y);
    const dataTransfer = new DataTransfer();
    for (let n = 0; n < 6; n++) dataTransfer.items.add(new File([
      'FACTOR = 3\ndef run(inputs, params, context):\n    return inputs[0]\n',
    ], `round${round}_${n}.py`, {type: 'text/x-python'}));
    const start = performance.now();
    for (const type of ['dragover', 'drop']) {
      const event = new DragEvent(type, {bubbles:true, cancelable:true, dataTransfer, clientX:x, clientY:y});
      target.dispatchEvent(event);
      if (!event.defaultPrevented) throw Error(`Canvas rejected ${type} over ${target.tagName}`);
    }
    await wait(() => count() === 6);
    results.push({round:round+1, target:target.tagName, nodes:count(), milliseconds:Math.round(performance.now()-start)});
    const pane = document.querySelector('.react-flow__pane');
    pane.dispatchEvent(new KeyboardEvent('keydown', {key:'a', code:'KeyA', ctrlKey:true, bubbles:true, cancelable:true}));
    await wait(() => document.querySelectorAll('.react-flow__node.selected').length === 6);
    pane.dispatchEvent(new KeyboardEvent('keyup', {key:'a', code:'KeyA', ctrlKey:true, bubbles:true}));
    pane.dispatchEvent(new KeyboardEvent('keydown', {key:'Delete', code:'Delete', bubbles:true, cancelable:true}));
    await wait(() => count() === 0);
    pane.dispatchEvent(new KeyboardEvent('keyup', {key:'Delete', code:'Delete', bubbles:true}));
    await wait(() => !!document.querySelector('.canvas-empty'));
  }
  return results;
})();
